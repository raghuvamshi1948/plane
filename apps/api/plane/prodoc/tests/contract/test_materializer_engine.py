# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Tests for the materialization planner and executor.

`build_plan` is a pure function: every happy-path assertion on
expansion counts, date math, dependency rewiring, and slug validation
runs without a single database write beyond fixture setup. The wet-run
tests drive `materialize` through a real transaction and assert the
expected `Issue` / `Module` / `IssueRelation` rows exist.

The cascade-suppression test is the load-bearing one: it materializes
a template that creates a blocker→blocked edge, then in the *same*
test (with the cascade receiver still installed) updates the blocker's
target date and asserts the downstream issue moves. This proves the
`cascade_suppressed()` context manager is scoped to the materializer
block and does not leak — Ext 2 keeps working after Ext 3 runs.
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.db import transaction

from plane.db.models import Issue, IssueRelation, Module, ModuleIssue
from plane.prodoc.materialization import (
    MaterializationValidationError,
    build_plan,
)
from plane.prodoc.materialization.engine import materialize
from plane.prodoc.models import (
    ProdocMigrationRequirement,
    ProdocSite,
    ProdocTemplate,
    ProdocTemplateSection,
    ProdocTemplateTask,
    ProdocTemplateTaskDependency,
    ProdocThirdPartyTool,
    ProdocWave,
    ProdocWaveSite,
)
from plane.prodoc.signals.cascade import cascade_suppressed


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------


@pytest.fixture
def template(db, workspace):
    return ProdocTemplate.objects.create(
        workspace=workspace,
        slug="mgm",
        version="1.0",
        name="MGM Phase 1",
    )


@pytest.fixture
def section(db, template):
    return ProdocTemplateSection.objects.create(
        template=template, name="Kickoff", order=1
    )


def _make_task(template, section, slug, **kwargs):
    defaults = dict(
        title=slug.replace("-", " ").title(),
        description="",
        offset_days=0,
        duration_days=2,
        role_key="admin",
        sla_hours=None,
        repeat_per_site=False,
        repeat_per_wave=False,
        dependency_mode="all",
        order=1,
        migration_requirement_slugs=[],
        third_party_tool_slugs=[],
    )
    defaults.update(kwargs)
    return ProdocTemplateTask.objects.create(
        template=template, section=section, slug=slug, **defaults
    )


@pytest.fixture
def sites(db, workspace, project):
    s1 = ProdocSite.objects.create(
        workspace=workspace, project=project, name="Hospital One", code="H1"
    )
    s2 = ProdocSite.objects.create(
        workspace=workspace, project=project, name="Hospital Two", code="H2"
    )
    s3 = ProdocSite.objects.create(
        workspace=workspace, project=project, name="Hospital Three", code="H3"
    )
    return [s1, s2, s3]


@pytest.fixture
def waves(db, workspace, project, sites):
    w1 = ProdocWave.objects.create(
        workspace=workspace,
        project=project,
        name="Wave Alpha",
        order=1,
        start_offset_days=0,
    )
    w2 = ProdocWave.objects.create(
        workspace=workspace,
        project=project,
        name="Wave Beta",
        order=2,
        start_offset_days=10,
    )
    # Wave Alpha has sites H1, H2. Wave Beta has site H3.
    ProdocWaveSite.objects.create(wave=w1, site=sites[0])
    ProdocWaveSite.objects.create(wave=w1, site=sites[1])
    ProdocWaveSite.objects.create(wave=w2, site=sites[2])
    return [w1, w2]


START_DATE = date(2026, 4, 6)  # A Monday


# ---------------------------------------------------------------------
# Pure-function planner tests
# ---------------------------------------------------------------------


@pytest.mark.contract
class TestBuildPlanHappyPath:
    @pytest.mark.django_db
    def test_no_expansion_single_work_item_per_task(
        self, template, section, project
    ):
        _make_task(template, section, "kickoff", offset_days=0, duration_days=3)
        _make_task(template, section, "signoff", offset_days=5, duration_days=1)

        plan = build_plan(template, project, START_DATE, sites=[], waves=[])

        assert len(plan.work_items) == 2
        assert plan.work_items[0].title == "Kickoff"
        assert plan.work_items[0].start_date == START_DATE
        # 3 business days from Mon Apr 6 = Thu Apr 9
        assert plan.work_items[0].target_date == date(2026, 4, 9)
        # offset 5 from Mon Apr 6 = Mon Apr 13; +1 day = Tue Apr 14
        assert plan.work_items[1].start_date == date(2026, 4, 13)
        assert plan.work_items[1].target_date == date(2026, 4, 14)

    @pytest.mark.django_db
    def test_per_site_expansion(self, template, section, project, sites):
        _make_task(template, section, "provision", repeat_per_site=True)

        plan = build_plan(template, project, START_DATE, sites=sites, waves=[])

        assert len(plan.work_items) == 3
        codes = sorted(w.site_code for w in plan.work_items)
        assert codes == ["H1", "H2", "H3"]
        # All three share the same dates (no wave offset applied).
        assert all(w.start_date == START_DATE for w in plan.work_items)

    @pytest.mark.django_db
    def test_per_wave_expansion_applies_wave_offset(
        self, template, section, project, sites, waves
    ):
        _make_task(template, section, "wave-brief", repeat_per_wave=True)

        plan = build_plan(
            template, project, START_DATE, sites=sites, waves=waves
        )

        assert len(plan.work_items) == 2
        by_wave = {w.wave_name: w for w in plan.work_items}
        # Wave Alpha (offset 0) starts on project start.
        assert by_wave["Wave Alpha"].start_date == START_DATE
        # Wave Beta (offset 10 working days) starts 10 Mon-Fri days later.
        # Mon Apr 6 + 10 biz = Mon Apr 20
        assert by_wave["Wave Beta"].start_date == date(2026, 4, 20)

    @pytest.mark.django_db
    def test_mixed_expansion_is_cartesian_over_wave_members(
        self, template, section, project, sites, waves
    ):
        _make_task(
            template,
            section,
            "go-live",
            repeat_per_site=True,
            repeat_per_wave=True,
        )

        plan = build_plan(
            template, project, START_DATE, sites=sites, waves=waves
        )

        # Wave Alpha has 2 member sites, Wave Beta has 1 → 3 total.
        assert len(plan.work_items) == 3
        pairs = {(w.wave_name, w.site_code) for w in plan.work_items}
        assert pairs == {
            ("Wave Alpha", "H1"),
            ("Wave Alpha", "H2"),
            ("Wave Beta", "H3"),
        }


@pytest.mark.contract
class TestBuildPlanDependencyRewiring:
    @pytest.mark.django_db
    def test_dependency_mode_all_produces_cartesian_edges(
        self, template, section, project, sites
    ):
        upstream = _make_task(
            template, section, "survey", repeat_per_site=True
        )
        downstream = _make_task(
            template,
            section,
            "report",
            repeat_per_site=True,
            dependency_mode="all",
        )
        ProdocTemplateTaskDependency.objects.create(
            upstream=upstream, downstream=downstream
        )

        plan = build_plan(template, project, START_DATE, sites=sites, waves=[])

        # 3 upstream × 3 downstream = 9 edges under "all".
        assert len(plan.relations) == 9

    @pytest.mark.django_db
    def test_dependency_mode_same_site_links_only_matching_sites(
        self, template, section, project, sites
    ):
        upstream = _make_task(
            template, section, "survey", repeat_per_site=True
        )
        downstream = _make_task(
            template,
            section,
            "report",
            repeat_per_site=True,
            dependency_mode="same_site",
        )
        ProdocTemplateTaskDependency.objects.create(
            upstream=upstream, downstream=downstream
        )

        plan = build_plan(template, project, START_DATE, sites=sites, waves=[])

        # Only H1→H1, H2→H2, H3→H3 edges.
        assert len(plan.relations) == 3
        for rel in plan.relations:
            up = plan.work_items[rel.upstream_index]
            dn = plan.work_items[rel.downstream_index]
            assert up.site_id == dn.site_id


@pytest.mark.contract
class TestBuildPlanValidation:
    @pytest.mark.django_db
    def test_unresolved_slug_raises_with_per_task_errors(
        self, template, section, project, workspace
    ):
        # Real requirement exists — tasks that reference it should be fine.
        ProdocMigrationRequirement.objects.create(
            workspace=workspace,
            slug="req-export",
            name="Export",
            category="data",
            default_owner_role="admin",
        )
        _make_task(
            template,
            section,
            "valid-task",
            migration_requirement_slugs=["req-export"],
        )
        _make_task(
            template,
            section,
            "bad-task",
            migration_requirement_slugs=["req-missing", "req-also-missing"],
            third_party_tool_slugs=["tool-ghost"],
        )

        with pytest.raises(MaterializationValidationError) as excinfo:
            build_plan(template, project, START_DATE, sites=[], waves=[])

        errors = excinfo.value.errors
        assert "bad-task" in errors
        assert "valid-task" not in errors
        joined = " ".join(errors["bad-task"])
        assert "req-missing" in joined
        assert "req-also-missing" in joined
        assert "tool-ghost" in joined


# ---------------------------------------------------------------------
# Wet-run executor tests
# ---------------------------------------------------------------------


@pytest.mark.contract
class TestMaterializeDryRun:
    @pytest.mark.django_db
    def test_dry_run_writes_nothing(
        self, template, section, project, sites, waves
    ):
        _make_task(
            template, section, "provision", repeat_per_site=True
        )
        plan = build_plan(
            template, project, START_DATE, sites=sites, waves=waves
        )

        issue_count_before = Issue.objects.count()
        module_count_before = Module.objects.count()
        relation_count_before = IssueRelation.objects.count()

        result = materialize(plan, project, dry_run=True)

        assert result is plan
        assert Issue.objects.count() == issue_count_before
        assert Module.objects.count() == module_count_before
        assert IssueRelation.objects.count() == relation_count_before
        # Every planned item stays unresolved (no issue_id assigned).
        assert all(w.issue_id is None for w in plan.work_items)


@pytest.mark.contract
class TestMaterializeWetRun:
    @pytest.mark.django_db
    def test_wet_run_creates_issues_modules_and_relations(
        self, template, section, project, sites, waves
    ):
        upstream = _make_task(
            template,
            section,
            "prep",
            offset_days=0,
            duration_days=2,
            repeat_per_wave=True,
        )
        downstream = _make_task(
            template,
            section,
            "launch",
            offset_days=5,
            duration_days=1,
            repeat_per_wave=True,
            dependency_mode="all",
        )
        ProdocTemplateTaskDependency.objects.create(
            upstream=upstream, downstream=downstream
        )

        plan = build_plan(
            template, project, START_DATE, sites=sites, waves=waves
        )

        with transaction.atomic():
            with cascade_suppressed():
                materialize(plan, project, dry_run=False)

        # 2 waves × 2 tasks = 4 issues.
        assert (
            Issue.objects.filter(project=project).count() == 4
        )
        # 2 modules (one per wave), names match.
        module_names = set(
            Module.objects.filter(project=project).values_list(
                "name", flat=True
            )
        )
        assert module_names == {"Wave Alpha", "Wave Beta"}
        # Each wave gets 2 ModuleIssue attachments (both tasks).
        assert ModuleIssue.objects.filter(module__project=project).count() == 4
        # Relations: "all" mode with 2 upstream × 2 downstream = 4.
        assert (
            IssueRelation.objects.filter(project=project).count() == 4
        )
        # Planned work items got their issue_id populated.
        assert all(w.issue_id is not None for w in plan.work_items)
        # Wave Beta's prep issue inherits wave offset=10 biz days.
        beta_prep = next(
            w
            for w in plan.work_items
            if w.wave_name == "Wave Beta" and w.template_task_slug == "prep"
        )
        # Mon Apr 6 + 10 biz days = Mon Apr 20
        issue = Issue.objects.get(id=beta_prep.issue_id)
        assert issue.start_date == date(2026, 4, 20)
        assert issue.target_date == date(2026, 4, 22)

    @pytest.mark.django_db
    def test_cascade_stays_active_after_materialization(
        self, template, section, project, sites, waves, issue_factory
    ):
        """The suppression context manager must not leak out of the
        materializer block — Ext 2's cascade has to keep working on
        subsequent saves in the same test/request."""
        upstream = _make_task(
            template,
            section,
            "prep",
            offset_days=0,
            duration_days=2,
            repeat_per_wave=True,
        )
        downstream = _make_task(
            template,
            section,
            "launch",
            offset_days=5,
            duration_days=1,
            repeat_per_wave=True,
            dependency_mode="all",
        )
        ProdocTemplateTaskDependency.objects.create(
            upstream=upstream, downstream=downstream
        )
        plan = build_plan(
            template, project, START_DATE, sites=sites, waves=waves
        )
        with transaction.atomic():
            with cascade_suppressed():
                materialize(plan, project, dry_run=False)

        # Pick one wave's prep (upstream) and launch (downstream), slip
        # prep forward, and assert launch moves via Ext 2's cascade.
        alpha_prep = next(
            w
            for w in plan.work_items
            if w.wave_name == "Wave Alpha" and w.template_task_slug == "prep"
        )
        alpha_launch = next(
            w
            for w in plan.work_items
            if w.wave_name == "Wave Alpha"
            and w.template_task_slug == "launch"
        )
        prep_issue = Issue.objects.get(id=alpha_prep.issue_id)
        launch_issue = Issue.objects.get(id=alpha_launch.issue_id)

        original_launch_target = launch_issue.target_date
        # Slip prep forward by 5 calendar days (~3 working days) with
        # the cascade feature flag enabled. If the suppression CM leaked
        # beyond the materializer block, the cascade would not fire and
        # launch_issue.target_date would stay put.
        with patch(
            "plane.prodoc.signals.dependency.get_configuration_value",
            return_value=("1",),
        ):
            prep_issue.target_date = prep_issue.target_date + timedelta(days=5)
            prep_issue.save(update_fields=["target_date"])

        launch_issue.refresh_from_db()
        assert launch_issue.target_date > original_launch_target


@pytest.mark.contract
class TestMaterializerWorkspaceSafety:
    @pytest.mark.django_db
    def test_cross_workspace_requirement_slugs_do_not_resolve(
        self, template, section, project, workspace, second_workspace
    ):
        # Put the requirement in the *other* workspace only.
        ProdocMigrationRequirement.objects.create(
            workspace=second_workspace["workspace"],
            slug="req-foreign",
            name="Foreign",
            category="data",
            default_owner_role="admin",
        )
        _make_task(
            template,
            section,
            "uses-foreign",
            migration_requirement_slugs=["req-foreign"],
        )

        with pytest.raises(MaterializationValidationError) as excinfo:
            build_plan(template, project, START_DATE, sites=[], waves=[])
        assert "uses-foreign" in excinfo.value.errors
