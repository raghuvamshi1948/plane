# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Model-layer tests for ProdocIssueLink and ProdocMaterializationJob.

The link sidecar is the C2 resolution for custom properties (plan
file): a OneToOne to `db.Issue` carrying the Prodoc-only metadata we
can't hang off the upstream model. The job row is the post-mortem
record the Celery task in commit 7 will drive through the state
machine.

This commit also wires `ProdocIssueLink` creation into the
materializer engine, so the tests here include an integration assertion
that a wet-run materialization produces one link per work item with
the right template_task / site / wave / M2M payload.
"""

from datetime import date

import pytest
from django.db import IntegrityError, transaction

from plane.db.models import Issue
from plane.prodoc.materialization import build_plan
from plane.prodoc.materialization.engine import materialize
from plane.prodoc.models import (
    ProdocIssueLink,
    ProdocMaterializationJob,
    ProdocMigrationRequirement,
    ProdocSite,
    ProdocTemplate,
    ProdocTemplateSection,
    ProdocTemplateTask,
    ProdocThirdPartyTool,
)
from plane.prodoc.signals.cascade import cascade_suppressed


@pytest.fixture
def template(db, workspace):
    return ProdocTemplate.objects.create(
        workspace=workspace, slug="t", version="1.0", name="T"
    )


@pytest.fixture
def section(db, template):
    return ProdocTemplateSection.objects.create(
        template=template, name="S", order=1
    )


@pytest.mark.contract
class TestProdocIssueLinkModel:
    @pytest.mark.django_db
    def test_sidecar_is_one_to_one(
        self, workspace, project, issue_factory
    ):
        issue = issue_factory(project)
        ProdocIssueLink.objects.create(
            issue=issue, workspace=workspace, project=project
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProdocIssueLink.objects.create(
                    issue=issue, workspace=workspace, project=project
                )

    @pytest.mark.django_db
    def test_m2m_requirements_and_tools_round_trip(
        self, workspace, project, issue_factory
    ):
        req = ProdocMigrationRequirement.objects.create(
            workspace=workspace,
            slug="req-one",
            name="One",
            category="data",
            default_owner_role="admin",
        )
        tool = ProdocThirdPartyTool.objects.create(
            workspace=workspace,
            slug="tool-one",
            name="Tool",
            category="crm",
            default_owner_role="admin",
        )
        issue = issue_factory(project)
        link = ProdocIssueLink.objects.create(
            issue=issue, workspace=workspace, project=project
        )
        link.migration_requirements.add(req)
        link.third_party_tools.add(tool)

        refreshed = ProdocIssueLink.objects.get(pk=link.pk)
        assert list(refreshed.migration_requirements.values_list("slug", flat=True)) == ["req-one"]
        assert list(refreshed.third_party_tools.values_list("slug", flat=True)) == ["tool-one"]

    @pytest.mark.django_db
    def test_workspace_scoped_filter_does_not_require_issue_join(
        self, workspace, project, issue_factory, second_workspace
    ):
        issue = issue_factory(project)
        ProdocIssueLink.objects.create(
            issue=issue, workspace=workspace, project=project
        )
        # Query scoped to the other workspace must not see it via the
        # denormalized workspace column alone (no join).
        qs = ProdocIssueLink.objects.filter(
            workspace=second_workspace["workspace"]
        )
        assert qs.count() == 0

    @pytest.mark.django_db
    def test_materializer_creates_one_link_per_work_item(
        self, workspace, project, template, section
    ):
        req = ProdocMigrationRequirement.objects.create(
            workspace=workspace,
            slug="req-export",
            name="Export",
            category="data",
            default_owner_role="admin",
        )
        ProdocTemplateTask.objects.create(
            template=template,
            section=section,
            slug="task-a",
            title="A",
            description="",
            offset_days=0,
            duration_days=1,
            role_key="admin",
            order=1,
            migration_requirement_slugs=["req-export"],
            third_party_tool_slugs=[],
        )
        ProdocTemplateTask.objects.create(
            template=template,
            section=section,
            slug="task-b",
            title="B",
            description="",
            offset_days=2,
            duration_days=1,
            role_key="admin",
            order=2,
            sla_hours=24,
        )

        plan = build_plan(
            template, project, date(2026, 4, 6), sites=[], waves=[]
        )
        with transaction.atomic():
            with cascade_suppressed():
                materialize(plan, project, dry_run=False)

        # Two issues, two links.
        assert Issue.objects.filter(project=project).count() == 2
        assert ProdocIssueLink.objects.filter(project=project).count() == 2

        link_a = ProdocIssueLink.objects.get(
            issue__name="A", project=project
        )
        assert link_a.template_task.slug == "task-a"
        assert list(
            link_a.migration_requirements.values_list("slug", flat=True)
        ) == ["req-export"]
        assert link_a.sla_hours is None

        link_b = ProdocIssueLink.objects.get(
            issue__name="B", project=project
        )
        assert link_b.template_task.slug == "task-b"
        assert link_b.sla_hours == 24
        assert link_b.migration_requirements.count() == 0


@pytest.mark.contract
class TestProdocMaterializationJobModel:
    @pytest.mark.django_db
    def test_status_transitions_queued_to_succeeded(
        self, workspace, project, template
    ):
        from django.utils import timezone

        job = ProdocMaterializationJob.objects.create(
            workspace=workspace,
            project=project,
            template=template,
            start_date=date(2026, 4, 6),
        )
        assert job.status == "queued"
        job.status = "running"
        job.started_at = timezone.now()
        job.save()
        job.status = "succeeded"
        job.finished_at = timezone.now()
        job.work_items_created = ["id-1", "id-2"]
        job.save()

        refreshed = ProdocMaterializationJob.objects.get(pk=job.pk)
        assert refreshed.status == "succeeded"
        assert refreshed.work_items_created == ["id-1", "id-2"]

    @pytest.mark.django_db
    def test_failed_job_persists_error_log_and_artifact_ids(
        self, workspace, project, template
    ):
        job = ProdocMaterializationJob.objects.create(
            workspace=workspace,
            project=project,
            template=template,
            start_date=date(2026, 4, 6),
            status="failed",
            error_log="Traceback...\nValueError: bad slug",
            work_items_created=["wi-1"],
            modules_created=["mod-1"],
            relations_created=[],
        )
        refreshed = ProdocMaterializationJob.objects.get(pk=job.pk)
        assert refreshed.status == "failed"
        assert "bad slug" in refreshed.error_log
        assert refreshed.work_items_created == ["wi-1"]
        assert refreshed.modules_created == ["mod-1"]
