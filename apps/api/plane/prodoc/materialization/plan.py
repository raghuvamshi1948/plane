"""
Pure-data materialization plan builder.

`build_plan` is a pure function: no DB writes, no side effects. It
produces a `Plan` object whose `work_items` list describes every work
item the wet-run engine would create, and whose `relations` list
describes every dependency edge. The dry-run API path returns this plan
as-is; the wet-run path hands it to `engine.materialize` inside an
atomic transaction.

Expansion rules (build plan §7.3 scenarios 3–5):

  - `repeat_per_site=False, repeat_per_wave=False`: 1 work item
  - `repeat_per_site=True,  repeat_per_wave=False`: 1 per site
  - `repeat_per_site=False, repeat_per_wave=True`:  1 per wave
  - `repeat_per_site=True,  repeat_per_wave=True`:  1 per (wave, site)
    where site is a member of the wave (via ProdocWaveSite)

Date computation:

  effective_offset = task.offset_days + (wave.start_offset_days if wave else 0)
  planned_start    = add_business_days(project_start_date, effective_offset, holidays)
  planned_target   = add_business_days(planned_start,      task.duration_days, holidays)

The holiday set comes from Ext 2's `resolve_calendar_for_project`, so
the materializer honours any per-project override the ops team has
configured.

Dependency rewiring (build plan scenario 6): for each
`ProdocTemplateTaskDependency`, the planner matches upstream expansions
to downstream expansions according to the downstream's
`dependency_mode`:

  - `all`:       every upstream expansion blocks every downstream expansion
  - `same_site`: only expansions that share a Site are linked (wave-only
    tasks are treated as any-site, so a per-wave upstream matches every
    per-site downstream in the same wave).

Validation:

  Every `migration_requirement_slugs` / `third_party_tool_slugs` entry is
  resolved against the workspace's catalog before any date math runs. An
  unresolved slug raises `MaterializationValidationError` listing every
  unknown slug grouped by task, so dry-run returns a precise error
  without ever touching the database.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional
from uuid import UUID

from plane.prodoc.models import (
    ProdocMigrationRequirement,
    ProdocThirdPartyTool,
    ProdocWaveSite,
)
from plane.prodoc.scheduling.business_days import add_business_days
from plane.prodoc.scheduling.calendar_resolver import (
    parse_holidays,
    resolve_calendar_for_project,
)


class MaterializationValidationError(Exception):
    """Raised when a template cannot be materialized as-authored.

    Carries a structured `errors` dict so callers can return a precise
    422 to API clients instead of a bare string.
    """

    def __init__(self, errors):
        self.errors = errors
        super().__init__(self._render(errors))

    @staticmethod
    def _render(errors):
        lines = []
        for task_slug, messages in errors.items():
            for msg in messages:
                lines.append(f"{task_slug}: {msg}")
        return "; ".join(lines) or "materialization validation failed"


@dataclass
class PlannedWorkItem:
    """A single work item the materializer will create on wet run.

    Identity within a plan: `(template_task_id, wave_id, site_id)`.
    `site_id` and `wave_id` are `None` for non-expanded tasks.
    """

    template_task_id: UUID
    template_task_slug: str
    title: str
    description: str
    start_date: date
    target_date: date
    role_key: str
    sla_hours: Optional[int]
    wave_id: Optional[UUID]
    wave_name: Optional[str]
    site_id: Optional[UUID]
    site_code: Optional[str]
    migration_requirement_ids: list
    third_party_tool_ids: list
    # Populated on wet run only; stays None in dry run output.
    issue_id: Optional[UUID] = None


@dataclass
class PlannedRelation:
    """A single blocked_by edge the materializer will create.

    `upstream_index` / `downstream_index` point into
    `Plan.work_items` by position — stable because the list is built
    once and never reordered.
    """

    upstream_index: int
    downstream_index: int


@dataclass
class Plan:
    template_id: UUID
    project_id: UUID
    workspace_id: UUID
    start_date: date
    work_items: list = field(default_factory=list)
    relations: list = field(default_factory=list)
    module_specs: list = field(default_factory=list)  # [(wave_id, name)] for wet run
    warnings: list = field(default_factory=list)


def _task_expansions(task, waves, sites, wave_to_sites):
    """Yield (wave_or_none, site_or_none) tuples for a given task.

    `wave_to_sites` is a mapping of wave_id -> list of ProdocSite. When
    a task is both per_wave and per_site, we iterate each wave's member
    sites; sites that belong to no wave are not included in a both-flags
    expansion (they'd have no date to compute because there's no wave
    offset to apply).
    """
    if task.repeat_per_wave and task.repeat_per_site:
        for wave in waves:
            for site in wave_to_sites.get(wave.id, []):
                yield (wave, site)
    elif task.repeat_per_wave:
        for wave in waves:
            yield (wave, None)
    elif task.repeat_per_site:
        for site in sites:
            yield (None, site)
    else:
        yield (None, None)


def _resolve_slug_catalog(workspace_id, model, slugs):
    if not slugs:
        return {}, set()
    rows = model.objects.filter(
        workspace_id=workspace_id, slug__in=slugs, deleted_at__isnull=True
    ).values_list("slug", "id")
    by_slug = {slug: row_id for slug, row_id in rows}
    missing = set(slugs) - set(by_slug.keys())
    return by_slug, missing


def _decorated_title(base_title, wave, site):
    suffix_parts = []
    if wave is not None:
        suffix_parts.append(wave.name)
    if site is not None:
        suffix_parts.append(site.code)
    if suffix_parts:
        return f"{base_title} — {' · '.join(suffix_parts)}"
    return base_title


def build_plan(template, project, start_date, sites, waves):
    """Return a `Plan` describing the full materialization tree.

    Pure function: does not write to the DB. Performs all validation
    up-front so callers get a single, structured error rather than a
    half-built tree.
    """
    workspace_id = template.workspace_id

    # Load all tasks + dependencies up front so the planner is
    # database-light during expansion.
    tasks = list(
        template.tasks.filter(deleted_at__isnull=True).order_by("order")
    )
    task_by_id = {t.id: t for t in tasks}
    # ProdocTemplateTaskDependency lives in plane.prodoc.models but we
    # import lazily here to avoid a circular import at module-load time.
    from plane.prodoc.models import ProdocTemplateTaskDependency

    dependencies = list(
        ProdocTemplateTaskDependency.objects.filter(
            upstream__template=template,
            downstream__template=template,
            deleted_at__isnull=True,
        ).values_list("upstream_id", "downstream_id")
    )

    # Build wave -> list of member sites map in a single query.
    wave_to_sites = {}
    if waves:
        wave_ids = [w.id for w in waves]
        for ws in ProdocWaveSite.objects.filter(
            wave_id__in=wave_ids, deleted_at__isnull=True
        ).select_related("site"):
            wave_to_sites.setdefault(ws.wave_id, []).append(ws.site)

    # Resolve every task's slug lists up front. Errors go into a single
    # dict keyed by task slug so the caller sees all problems at once.
    all_req_slugs = set()
    all_tool_slugs = set()
    for task in tasks:
        all_req_slugs.update(task.migration_requirement_slugs or [])
        all_tool_slugs.update(task.third_party_tool_slugs or [])
    req_by_slug, _ = _resolve_slug_catalog(
        workspace_id, ProdocMigrationRequirement, list(all_req_slugs)
    )
    tool_by_slug, _ = _resolve_slug_catalog(
        workspace_id, ProdocThirdPartyTool, list(all_tool_slugs)
    )

    errors = {}
    for task in tasks:
        missing_reqs = [
            slug
            for slug in (task.migration_requirement_slugs or [])
            if slug not in req_by_slug
        ]
        missing_tools = [
            slug
            for slug in (task.third_party_tool_slugs or [])
            if slug not in tool_by_slug
        ]
        if missing_reqs:
            errors.setdefault(task.slug, []).append(
                f"unknown migration requirement slugs: {sorted(missing_reqs)}"
            )
        if missing_tools:
            errors.setdefault(task.slug, []).append(
                f"unknown third party tool slugs: {sorted(missing_tools)}"
            )
    if errors:
        raise MaterializationValidationError(errors)

    # Resolve the calendar once per (project, workspace) — same holiday
    # set applies to every computed date in this materialization.
    calendar = resolve_calendar_for_project(
        project_id=project.id, workspace_id=workspace_id
    )
    holidays = parse_holidays(calendar.holidays) if calendar else set()

    plan = Plan(
        template_id=template.id,
        project_id=project.id,
        workspace_id=workspace_id,
        start_date=start_date,
    )

    # Module specs: one per wave, mirrored in the upstream `Module`
    # table on wet run. Waves without a mirror module yet (plane_module
    # is None) will have one created.
    for wave in waves:
        plan.module_specs.append(
            {
                "wave_id": wave.id,
                "name": wave.name,
                "existing_module_id": wave.plane_module_id,
            }
        )

    # Expansion index: template_task_id -> list of (work_items index).
    # Used in the dependency pass to build PlannedRelation edges.
    expansions_by_task: dict = {}

    for task in tasks:
        task_req_ids = [
            req_by_slug[s] for s in (task.migration_requirement_slugs or [])
        ]
        task_tool_ids = [
            tool_by_slug[s] for s in (task.third_party_tool_slugs or [])
        ]

        for wave, site in _task_expansions(task, waves, sites, wave_to_sites):
            effective_offset = task.offset_days + (
                wave.start_offset_days if wave is not None else 0
            )
            planned_start = add_business_days(
                start_date, effective_offset, holidays
            )
            planned_target = add_business_days(
                planned_start, task.duration_days, holidays
            )

            work_item = PlannedWorkItem(
                template_task_id=task.id,
                template_task_slug=task.slug,
                title=_decorated_title(task.title, wave, site),
                description=task.description,
                start_date=planned_start,
                target_date=planned_target,
                role_key=task.role_key,
                sla_hours=task.sla_hours,
                wave_id=wave.id if wave else None,
                wave_name=wave.name if wave else None,
                site_id=site.id if site else None,
                site_code=site.code if site else None,
                migration_requirement_ids=task_req_ids,
                third_party_tool_ids=task_tool_ids,
            )
            plan.work_items.append(work_item)
            expansions_by_task.setdefault(task.id, []).append(
                len(plan.work_items) - 1
            )

    # Dependency rewiring. Every downstream expansion gets a blocked_by
    # edge for every matched upstream expansion per dependency_mode.
    for upstream_id, downstream_id in dependencies:
        upstream_task = task_by_id.get(upstream_id)
        downstream_task = task_by_id.get(downstream_id)
        if upstream_task is None or downstream_task is None:
            continue
        upstream_indices = expansions_by_task.get(upstream_id, [])
        downstream_indices = expansions_by_task.get(downstream_id, [])
        mode = downstream_task.dependency_mode

        for dn_idx in downstream_indices:
            dn = plan.work_items[dn_idx]
            for up_idx in upstream_indices:
                up = plan.work_items[up_idx]
                if mode == "same_site":
                    # Only link when both share a site, OR one side has
                    # no site (per-wave task) and the wave matches.
                    if dn.site_id is not None and up.site_id is not None:
                        if dn.site_id != up.site_id:
                            continue
                    elif dn.wave_id is not None and up.wave_id is not None:
                        if dn.wave_id != up.wave_id:
                            continue
                plan.relations.append(
                    PlannedRelation(
                        upstream_index=up_idx, downstream_index=dn_idx
                    )
                )

    return plan
