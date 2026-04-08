# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Tests for the prodoc_materialize_project Celery task.

The task is the thin wrapper around the commit-5 engine that adds
state-machine transitions, cascade suppression, and failure bookkeeping.
Tests exercise the full wrapper — happy path (queued → succeeded,
template locked), failure path (atomic rollback, separate transaction
for the error record), and the cascade suppression integration (webhook
dispatch MUST NOT fire for relations created during materialization,
because they're being constructed, not slipped).

The test harness runs Celery eagerly (CELERY_TASK_ALWAYS_EAGER=True in
plane.settings.test) so `.delay()` runs synchronously inside the test
and exceptions propagate back.
"""

from datetime import date
from unittest.mock import patch

import pytest
from django.db import transaction

from plane.db.models import Issue, IssueRelation, Module
from plane.prodoc.models import (
    ProdocMaterializationJob,
    ProdocTemplate,
    ProdocTemplateSection,
    ProdocTemplateTask,
    ProdocTemplateTaskDependency,
)
from plane.prodoc.tasks import prodoc_materialize_project


@pytest.fixture
def template(db, workspace):
    return ProdocTemplate.objects.create(
        workspace=workspace, slug="mgm", version="1.0", name="MGM"
    )


@pytest.fixture
def section(db, template):
    return ProdocTemplateSection.objects.create(
        template=template, name="Kickoff", order=1
    )


@pytest.fixture
def populated_template(db, template, section):
    upstream = ProdocTemplateTask.objects.create(
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
    downstream = ProdocTemplateTask.objects.create(
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
    ProdocTemplateTaskDependency.objects.create(
        upstream=upstream, downstream=downstream
    )
    return template


@pytest.fixture
def job(db, workspace, project, populated_template):
    return ProdocMaterializationJob.objects.create(
        workspace=workspace,
        project=project,
        template=populated_template,
        start_date=date(2026, 4, 6),
    )


@pytest.mark.contract
class TestMaterializationTaskHappyPath:
    @pytest.mark.django_db
    def test_queued_to_succeeded_creates_work_items_and_locks_template(
        self, job, project, populated_template
    ):
        prodoc_materialize_project(job.id)

        refreshed = ProdocMaterializationJob.objects.get(id=job.id)
        assert refreshed.status == "succeeded"
        assert refreshed.started_at is not None
        assert refreshed.finished_at is not None
        assert Issue.objects.filter(project=project).count() == 2
        assert IssueRelation.objects.filter(project=project).count() == 1
        # Template is now locked — commit 8's PATCH API enforces the 409.
        populated_template.refresh_from_db()
        assert populated_template.is_locked is True

    @pytest.mark.django_db
    def test_cascade_webhook_does_not_fire_during_materialization(
        self, job, project
    ):
        """Ext 2's cascade walker dispatches `prodoc_dispatch_dependency_webhook`
        whenever a downstream issue slips. Constructing a relation
        edge is not a slip — the walker must be suppressed for the
        engine block, so no webhook should be queued."""
        with patch(
            "plane.prodoc.signals.cascade.prodoc_dispatch_dependency_webhook.delay"
        ) as mock_dispatch:
            prodoc_materialize_project(job.id)
        assert mock_dispatch.call_count == 0


@pytest.mark.contract
class TestMaterializationTaskFailurePath:
    @pytest.mark.django_db
    def test_engine_exception_rolls_back_work_but_writes_failed_status(
        self, job, project, populated_template
    ):
        """Inject a failure mid-engine. The atomic block must unwind
        (zero rows committed), AND the separate bookkeeping block must
        still write status='failed' + error_log."""
        issue_count_before = Issue.objects.count()
        module_count_before = Module.objects.count()

        with patch(
            "plane.prodoc.materialization.engine.Issue.objects.create",
            side_effect=RuntimeError("kaboom"),
        ):
            with pytest.raises(RuntimeError, match="kaboom"):
                prodoc_materialize_project(job.id)

        refreshed = ProdocMaterializationJob.objects.get(id=job.id)
        assert refreshed.status == "failed"
        assert "kaboom" in refreshed.error_log
        assert refreshed.finished_at is not None
        # Nothing committed — atomic block rolled back the partial work.
        assert Issue.objects.count() == issue_count_before
        assert Module.objects.count() == module_count_before
        # Template stays unlocked on failure.
        populated_template.refresh_from_db()
        assert populated_template.is_locked is False

    @pytest.mark.django_db
    def test_validation_error_fails_job_cleanly(
        self, workspace, project, template, section
    ):
        """An unresolved slug raises MaterializationValidationError
        from build_plan *inside* the atomic block. Same rollback path,
        same bookkeeping."""
        ProdocTemplateTask.objects.create(
            template=template,
            section=section,
            slug="bad",
            title="Bad",
            description="",
            offset_days=0,
            duration_days=1,
            role_key="admin",
            order=1,
            migration_requirement_slugs=["req-does-not-exist"],
        )
        job = ProdocMaterializationJob.objects.create(
            workspace=workspace,
            project=project,
            template=template,
            start_date=date(2026, 4, 6),
        )
        from plane.prodoc.materialization import MaterializationValidationError

        with pytest.raises(MaterializationValidationError):
            prodoc_materialize_project(job.id)

        refreshed = ProdocMaterializationJob.objects.get(id=job.id)
        assert refreshed.status == "failed"
        assert "req-does-not-exist" in refreshed.error_log
