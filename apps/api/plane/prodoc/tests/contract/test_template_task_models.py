# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Model-layer tests for ProdocTemplateTask and
ProdocTemplateTaskDependency.

Verifies (template, slug) uniqueness, the self-dependency CHECK
constraint, workspace isolation via template__workspace, and the
migration_requirement_slugs JSONField round-trip.
"""

import pytest
from django.db import IntegrityError, transaction

from plane.prodoc.models import (
    ProdocTemplate,
    ProdocTemplateSection,
    ProdocTemplateTask,
    ProdocTemplateTaskDependency,
)


def _make_template(workspace, slug="t", version="1.0"):
    template = ProdocTemplate.objects.create(
        workspace=workspace, slug=slug, version=version, name=slug
    )
    section = ProdocTemplateSection.objects.create(
        template=template, name="Default", order=1
    )
    return template, section


def _make_task(template, section, slug, **overrides):
    defaults = dict(
        template=template,
        section=section,
        slug=slug,
        title=slug.title(),
        offset_days=0,
        duration_days=1,
        role_key="admin",
        order=1,
    )
    defaults.update(overrides)
    return ProdocTemplateTask.objects.create(**defaults)


@pytest.mark.contract
class TestProdocTemplateTaskModel:
    @pytest.mark.django_db
    def test_template_slug_uniqueness_enforced(self, workspace):
        template, section = _make_template(workspace)
        _make_task(template, section, "provision-users", order=1)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                _make_task(template, section, "provision-users", order=2)

    @pytest.mark.django_db
    def test_same_slug_different_template_allowed(self, workspace):
        t1, s1 = _make_template(workspace, slug="a")
        t2, s2 = _make_template(workspace, slug="b")
        _make_task(t1, s1, "provision-users")
        _make_task(t2, s2, "provision-users")
        assert ProdocTemplateTask.objects.count() == 2

    @pytest.mark.django_db
    def test_self_dependency_rejected_by_check_constraint(self, workspace):
        template, section = _make_template(workspace)
        task = _make_task(template, section, "task-a")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProdocTemplateTaskDependency.objects.create(
                    upstream=task, downstream=task
                )

    @pytest.mark.django_db
    def test_dependency_uniqueness_enforced(self, workspace):
        template, section = _make_template(workspace)
        a = _make_task(template, section, "a", order=1)
        b = _make_task(template, section, "b", order=2)
        ProdocTemplateTaskDependency.objects.create(upstream=a, downstream=b)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProdocTemplateTaskDependency.objects.create(upstream=a, downstream=b)

    @pytest.mark.django_db
    def test_workspace_isolation_via_template_workspace(
        self, workspace, second_workspace
    ):
        t1, s1 = _make_template(workspace)
        _make_task(t1, s1, "task-a")
        other_qs = ProdocTemplateTask.objects.filter(
            template__workspace=second_workspace["workspace"]
        )
        assert other_qs.count() == 0

    @pytest.mark.django_db
    def test_migration_requirement_slugs_roundtrip(self, workspace):
        template, section = _make_template(workspace)
        task = _make_task(
            template,
            section,
            "task-a",
            migration_requirement_slugs=["req-data-export", "req-legacy-sso"],
            third_party_tool_slugs=["tool-salesforce"],
        )
        task.refresh_from_db()
        assert task.migration_requirement_slugs == [
            "req-data-export",
            "req-legacy-sso",
        ]
        assert task.third_party_tool_slugs == ["tool-salesforce"]
