# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""REST API tests for the materialize + job-poll endpoints.

Covers:
  - Dry-run returns the full plan tree and writes ZERO rows.
  - Wet-run returns 202 with a queued job and dispatches the Celery task.
  - After the eager task run (patched), work items exist, the template is
    locked, and the job is succeeded.
  - In-flight 409 when a queued/running job already exists.
  - Workspace isolation on the materialize path.
  - Feature flag disabled returns 404.
"""

from datetime import date
from unittest.mock import patch

import pytest
from rest_framework import status

from plane.db.models import Issue, IssueRelation, Module
from plane.prodoc.models import (
    ProdocIssueLink,
    ProdocMaterializationJob,
    ProdocTemplate,
    ProdocTemplateSection,
    ProdocTemplateTask,
    ProdocTemplateTaskDependency,
)
from plane.prodoc.tasks import prodoc_materialize_project


def _flag_on():
    return patch(
        "plane.prodoc.views.base.get_configuration_value",
        return_value=("1",),
    )


def _flag_off():
    return patch(
        "plane.prodoc.views.base.get_configuration_value",
        return_value=("0",),
    )


def _materialize_url(slug, project_id):
    return (
        f"/api/v1/prodoc/workspaces/{slug}/projects/{project_id}/materialize/"
    )


def _job_url(slug, project_id, job_id):
    return (
        f"/api/v1/prodoc/workspaces/{slug}/projects/{project_id}"
        f"/materialization-jobs/{job_id}/"
    )


@pytest.fixture
def populated_template(db, workspace):
    template = ProdocTemplate.objects.create(
        workspace=workspace, slug="mgm", version="1.0", name="MGM"
    )
    section = ProdocTemplateSection.objects.create(
        template=template, name="Kickoff", order=1
    )
    up = ProdocTemplateTask.objects.create(
        template=template,
        section=section,
        slug="prep",
        title="Prep",
        description="",
        offset_days=0,
        duration_days=2,
        role_key="admin",
        order=1,
    )
    down = ProdocTemplateTask.objects.create(
        template=template,
        section=section,
        slug="launch",
        title="Launch",
        description="",
        offset_days=5,
        duration_days=1,
        role_key="admin",
        order=2,
    )
    ProdocTemplateTaskDependency.objects.create(upstream=up, downstream=down)
    return template


@pytest.mark.contract
class TestProdocMaterializeDryRun:
    @pytest.mark.django_db
    def test_dry_run_returns_plan_tree_and_writes_nothing(
        self, api_key_client, workspace, project, populated_template
    ):
        issue_before = Issue.objects.count()
        rel_before = IssueRelation.objects.count()
        mod_before = Module.objects.count()
        link_before = ProdocIssueLink.objects.count()
        job_before = ProdocMaterializationJob.objects.count()

        with _flag_on():
            response = api_key_client.post(
                _materialize_url(workspace.slug, project.id),
                data={
                    "template_slug": "mgm",
                    "version": "1.0",
                    "start_date": "2026-04-06",
                    "dry_run": True,
                },
                format="json",
            )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["work_items"]) == 2
        assert len(response.data["relations"]) == 1
        # Zero writes.
        assert Issue.objects.count() == issue_before
        assert IssueRelation.objects.count() == rel_before
        assert Module.objects.count() == mod_before
        assert ProdocIssueLink.objects.count() == link_before
        assert ProdocMaterializationJob.objects.count() == job_before

    @pytest.mark.django_db
    def test_dry_run_unresolved_slug_returns_422(
        self, api_key_client, workspace, project
    ):
        template = ProdocTemplate.objects.create(
            workspace=workspace, slug="bad", version="1.0", name="Bad"
        )
        section = ProdocTemplateSection.objects.create(
            template=template, name="S", order=1
        )
        ProdocTemplateTask.objects.create(
            template=template,
            section=section,
            slug="t",
            title="T",
            description="",
            offset_days=0,
            duration_days=1,
            role_key="admin",
            order=1,
            migration_requirement_slugs=["req-missing"],
        )
        with _flag_on():
            response = api_key_client.post(
                _materialize_url(workspace.slug, project.id),
                data={
                    "template_slug": "bad",
                    "version": "1.0",
                    "start_date": "2026-04-06",
                    "dry_run": True,
                },
                format="json",
            )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "errors" in response.data


@pytest.mark.contract
class TestProdocMaterializeWetRun:
    @pytest.mark.django_db
    def test_wet_run_returns_202_and_dispatches_task(
        self, api_key_client, workspace, project, populated_template
    ):
        # Patch .delay to call synchronously so we can assert end state
        # without needing a live Celery broker.
        def _inline(job_id):
            prodoc_materialize_project(job_id)

        with _flag_on(), patch(
            "plane.prodoc.views.materialize.prodoc_materialize_project.delay",
            side_effect=_inline,
        ) as mock_delay:
            response = api_key_client.post(
                _materialize_url(workspace.slug, project.id),
                data={
                    "template_slug": "mgm",
                    "version": "1.0",
                    "start_date": "2026-04-06",
                    "dry_run": False,
                },
                format="json",
            )
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert mock_delay.call_count == 1
        job_id = response.data["job_id"]

        # Eager-run side effects:
        job = ProdocMaterializationJob.objects.get(id=job_id)
        assert job.status == "succeeded"
        assert Issue.objects.filter(project=project).count() == 2
        assert (
            IssueRelation.objects.filter(project=project).count() == 1
        )
        populated_template.refresh_from_db()
        assert populated_template.is_locked is True

    @pytest.mark.django_db
    def test_in_flight_job_returns_409(
        self, api_key_client, workspace, project, populated_template
    ):
        ProdocMaterializationJob.objects.create(
            workspace=workspace,
            project=project,
            template=populated_template,
            start_date=date(2026, 4, 6),
            status="running",
        )
        with _flag_on():
            response = api_key_client.post(
                _materialize_url(workspace.slug, project.id),
                data={
                    "template_slug": "mgm",
                    "version": "1.0",
                    "start_date": "2026-04-06",
                    "dry_run": False,
                },
                format="json",
            )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "job_id" in response.data


@pytest.mark.contract
class TestProdocMaterializeGuards:
    @pytest.mark.django_db
    def test_feature_flag_disabled_returns_404(
        self, api_key_client, workspace, project
    ):
        with _flag_off():
            response = api_key_client.post(
                _materialize_url(workspace.slug, project.id),
                data={
                    "template_slug": "mgm",
                    "version": "1.0",
                    "start_date": "2026-04-06",
                    "dry_run": True,
                },
                format="json",
            )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.django_db
    def test_workspace_isolation_on_materialize(
        self, api_key_client, workspace, project, second_workspace
    ):
        # Template belongs to the other workspace; this workspace's
        # caller must not see it.
        ProdocTemplate.objects.create(
            workspace=second_workspace["workspace"],
            slug="mgm",
            version="1.0",
            name="Foreign",
        )
        with _flag_on():
            response = api_key_client.post(
                _materialize_url(workspace.slug, project.id),
                data={
                    "template_slug": "mgm",
                    "version": "1.0",
                    "start_date": "2026-04-06",
                    "dry_run": True,
                },
                format="json",
            )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.contract
class TestProdocMaterializationJobDetail:
    @pytest.mark.django_db
    def test_job_detail_happy_path(
        self, api_key_client, workspace, project, populated_template
    ):
        job = ProdocMaterializationJob.objects.create(
            workspace=workspace,
            project=project,
            template=populated_template,
            start_date=date(2026, 4, 6),
        )
        with _flag_on():
            response = api_key_client.get(
                _job_url(workspace.slug, project.id, job.id)
            )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "queued"
