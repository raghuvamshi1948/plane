"""
Wet-run executor for a materialization `Plan`.

The executor is deliberately dumb: it does not branch on expansion
rules, does not compute dates, and does not validate slugs. Every
decision has already been made by `build_plan` (see `plan.py`); the
executor just walks the plan and writes rows in an order that respects
foreign-key dependencies.

Transaction boundary lives with the *caller*. The Celery task and the
management command both need to wrap this in their own
`transaction.atomic()` so they can pair it with their own bookkeeping
(job status transitions, rollback on failure). Opening the transaction
here would prevent the caller from writing "failed" status rows outside
the rolled-back block.

Cascade suppression is also the caller's responsibility. The materializer
writes ~60 `IssueRelation` rows and ~120 `Issue` rows; every one of
those `Issue.save()` calls would otherwise fire Ext 2's
`cascade_on_target_date_change` post_save receiver. During construction
that walker is pure waste — we are *building* the graph, not slipping
it. The caller wraps the engine in `with cascade_suppressed():` (see
`plane.prodoc.signals.cascade.cascade_suppressed`), and Ext 2's receiver
already early-returns when the thread-local guard is active.

Execution order (per build plan §7.7):

  1. Wave → Plane `Module` mirror (create or reuse existing).
  2. `Issue` rows for every `PlannedWorkItem` (single save() path so
     `sequence_id` is assigned correctly via the upstream advisory
     lock — `bulk_create` would skip this and every row would collide
     at `sequence_id=1`).
  3. `ModuleIssue` attachments for wave-bound issues.
  4. *(Deferred to commit 6: `ProdocIssueLink` sidecar rows.)*
  5. `IssueRelation` rows for every `PlannedRelation`, resolved via the
     position indexes the planner baked in.
  6. (Optional) `IssueAssignee` rows via `role_resolver`. Zero matches
     is a warning, not an error — the team may not have staffed the
     role yet.

The `job` parameter is duck-typed for now: it only needs three mutable
list attributes — `work_items_created`, `modules_created`,
`relations_created` — populated as we go so the Celery task's rollback
path (commit 7) can walk and soft-delete on failure. The real
`ProdocMaterializationJob` model arrives in commit 6.
"""

from plane.db.models import Issue, IssueAssignee, IssueRelation, Module, ModuleIssue
from plane.prodoc.materialization.role_resolver import resolve_assignees


class _NullJob:
    """Duck-typed stand-in when the caller doesn't have a real job row.

    Tests and the management command use this so the engine can be
    exercised without materializing `ProdocMaterializationJob` (commit 6)
    first. Production callers always pass a real row.
    """

    def __init__(self):
        self.work_items_created = []
        self.modules_created = []
        self.relations_created = []
        self.error_log = ""


def materialize(plan, project, job=None, *, dry_run=False):
    """Execute a `Plan` against the database.

    Caller contract:
        - Wrap this call in `transaction.atomic()` (or don't, for
          dry runs — but then pass `dry_run=True` explicitly).
        - Wrap wet runs in `cascade_suppressed()` so Ext 2's post_save
          cascade walker doesn't re-traverse the graph on every Issue
          save.

    Returns the `Plan` (with `issue_id` populated on every
    `PlannedWorkItem` for wet runs, untouched for dry runs).
    """
    if dry_run:
        return plan

    if job is None:
        job = _NullJob()

    # Step 1: Plane Module mirror per wave. `existing_module_id` is set
    # by build_plan when the wave already has `plane_module` attached —
    # reuse the row instead of creating a duplicate.
    module_by_wave = {}
    for spec in plan.module_specs:
        wave_id = spec["wave_id"]
        existing = spec.get("existing_module_id")
        if existing:
            module = Module.objects.filter(
                id=existing, deleted_at__isnull=True
            ).first()
        else:
            module = None
        if module is None:
            module = Module.objects.create(
                name=spec["name"],
                project=project,
                workspace=project.workspace,
                start_date=plan.start_date,
            )
            job.modules_created.append(str(module.id))
            # Write the mirror id back onto the wave so subsequent
            # materializations reuse it (build plan §7.2 idempotency).
            from plane.prodoc.models import ProdocWave

            ProdocWave.objects.filter(id=wave_id).update(plane_module=module)
        module_by_wave[wave_id] = module

    # Step 2 + 3: Issues, and their ModuleIssue attachment when wave-bound.
    # role_resolver is cached per role_key so we don't re-query per item.
    assignees_by_role = {}
    for wi in plan.work_items:
        if wi.role_key not in assignees_by_role:
            assignees_by_role[wi.role_key] = resolve_assignees(
                project, wi.role_key, job=job
            )

        issue = Issue.objects.create(
            name=wi.title,
            description_html=wi.description or "<p></p>",
            project=project,
            workspace=project.workspace,
            start_date=wi.start_date,
            target_date=wi.target_date,
        )
        wi.issue_id = issue.id
        job.work_items_created.append(str(issue.id))

        for user in assignees_by_role[wi.role_key]:
            IssueAssignee.objects.create(
                issue=issue,
                assignee=user,
                project=project,
                workspace=project.workspace,
            )

        if wi.wave_id is not None and wi.wave_id in module_by_wave:
            ModuleIssue.objects.create(
                module=module_by_wave[wi.wave_id],
                issue=issue,
                project=project,
                workspace=project.workspace,
            )

    # Step 5: IssueRelation edges. `blocked_by` semantics: the
    # `issue` is the downstream (blocked one), `related_issue` is the
    # upstream (the blocker). This matches Ext 2's cascade walker in
    # `signals/cascade.py` which filters `related_issue_id=<blocker>`
    # to find downstream issues.
    for rel in plan.relations:
        downstream_wi = plan.work_items[rel.downstream_index]
        upstream_wi = plan.work_items[rel.upstream_index]
        relation = IssueRelation.objects.create(
            issue_id=downstream_wi.issue_id,
            related_issue_id=upstream_wi.issue_id,
            relation_type="blocked_by",
            project=project,
            workspace=project.workspace,
        )
        job.relations_created.append(str(relation.id))

    return plan
