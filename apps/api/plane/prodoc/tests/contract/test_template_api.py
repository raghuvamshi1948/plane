# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""REST API tests for /api/v1/prodoc/.../templates/ and nested resources.

Covers templates, sections, tasks, and dependencies end-to-end: CRUD
happy paths, locked-template 409s, dependency cycle 409, slug
validation on tasks, workspace isolation, and feature-flag 404.
"""

from unittest.mock import patch

import pytest
from rest_framework import status

from plane.prodoc.models import (
    ProdocMigrationRequirement,
    ProdocTemplate,
    ProdocTemplateSection,
    ProdocTemplateTask,
    ProdocTemplateTaskDependency,
)


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


def _templates_url(slug):
    return f"/api/v1/prodoc/workspaces/{slug}/templates/"


def _template_url(slug, template_id):
    return f"/api/v1/prodoc/workspaces/{slug}/templates/{template_id}/"


def _sections_url(slug, template_id):
    return f"/api/v1/prodoc/workspaces/{slug}/templates/{template_id}/sections/"


def _tasks_url(slug, template_id):
    return f"/api/v1/prodoc/workspaces/{slug}/templates/{template_id}/tasks/"


def _deps_url(slug, template_id):
    return f"/api/v1/prodoc/workspaces/{slug}/templates/{template_id}/dependencies/"


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
class TestProdocTemplateAPI:
    @pytest.mark.django_db
    def test_create_and_list_template(self, api_key_client, workspace):
        with _flag_on():
            response = api_key_client.post(
                _templates_url(workspace.slug),
                data={
                    "slug": "onboarding",
                    "version": "1.0",
                    "name": "Onboarding",
                },
                format="json",
            )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["is_locked"] is False

        with _flag_on():
            response = api_key_client.get(_templates_url(workspace.slug))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    @pytest.mark.django_db
    def test_patch_locked_template_returns_409(
        self, api_key_client, workspace, template
    ):
        template.is_locked = True
        template.save(update_fields=["is_locked"])
        with _flag_on():
            response = api_key_client.patch(
                _template_url(workspace.slug, template.id),
                data={"name": "Updated"},
                format="json",
            )
        assert response.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.django_db
    def test_feature_flag_disabled_returns_404(
        self, api_key_client, workspace
    ):
        with _flag_off():
            response = api_key_client.get(_templates_url(workspace.slug))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.django_db
    def test_workspace_isolation_list(
        self, api_key_client, workspace, second_workspace
    ):
        ProdocTemplate.objects.create(
            workspace=second_workspace["workspace"],
            slug="foreign",
            version="1.0",
            name="Foreign",
        )
        with _flag_on():
            response = api_key_client.get(_templates_url(workspace.slug))
        assert response.status_code == status.HTTP_200_OK
        names = [row["name"] for row in response.data]
        assert "Foreign" not in names


@pytest.mark.contract
class TestProdocTemplateSectionAPI:
    @pytest.mark.django_db
    def test_create_section(self, api_key_client, workspace, template):
        with _flag_on():
            response = api_key_client.post(
                _sections_url(workspace.slug, template.id),
                data={"name": "Kickoff", "order": 1},
                format="json",
            )
        assert response.status_code == status.HTTP_201_CREATED

    @pytest.mark.django_db
    def test_create_section_on_locked_template_returns_409(
        self, api_key_client, workspace, template
    ):
        template.is_locked = True
        template.save(update_fields=["is_locked"])
        with _flag_on():
            response = api_key_client.post(
                _sections_url(workspace.slug, template.id),
                data={"name": "Late", "order": 1},
                format="json",
            )
        assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.contract
class TestProdocTemplateTaskAPI:
    @pytest.mark.django_db
    def test_create_task_happy_path(
        self, api_key_client, workspace, template, section
    ):
        ProdocMigrationRequirement.objects.create(
            workspace=workspace,
            slug="req-export",
            name="Export",
            category="data",
            default_owner_role="admin",
        )
        with _flag_on():
            response = api_key_client.post(
                _tasks_url(workspace.slug, template.id),
                data={
                    "section": str(section.id),
                    "slug": "task-a",
                    "title": "A",
                    "offset_days": 0,
                    "duration_days": 2,
                    "role_key": "admin",
                    "order": 1,
                    "migration_requirement_slugs": ["req-export"],
                },
                format="json",
            )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["migration_requirement_slugs"] == ["req-export"]

    @pytest.mark.django_db
    def test_create_task_rejects_unknown_slug(
        self, api_key_client, workspace, template, section
    ):
        with _flag_on():
            response = api_key_client.post(
                _tasks_url(workspace.slug, template.id),
                data={
                    "section": str(section.id),
                    "slug": "task-bad",
                    "title": "Bad",
                    "offset_days": 0,
                    "duration_days": 1,
                    "role_key": "admin",
                    "order": 1,
                    "migration_requirement_slugs": ["req-missing"],
                },
                format="json",
            )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "migration_requirement_slugs" in str(response.data)


@pytest.mark.contract
class TestProdocTemplateDependencyAPI:
    @pytest.mark.django_db
    def test_create_dependency_rejects_cycle(
        self, api_key_client, workspace, template, section
    ):
        def _mk(slug, order):
            return ProdocTemplateTask.objects.create(
                template=template,
                section=section,
                slug=slug,
                title=slug,
                description="",
                offset_days=0,
                duration_days=1,
                role_key="admin",
                order=order,
            )

        a = _mk("a", 1)
        b = _mk("b", 2)
        c = _mk("c", 3)

        # a → b, b → c
        ProdocTemplateTaskDependency.objects.create(upstream=a, downstream=b)
        ProdocTemplateTaskDependency.objects.create(upstream=b, downstream=c)

        # Attempting c → a would close the cycle a→b→c→a.
        with _flag_on():
            response = api_key_client.post(
                _deps_url(workspace.slug, template.id),
                data={"upstream": str(c.id), "downstream": str(a.id)},
                format="json",
            )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "cycle" in str(response.data).lower()

    @pytest.mark.django_db
    def test_create_dependency_happy_path(
        self, api_key_client, workspace, template, section
    ):
        t1 = ProdocTemplateTask.objects.create(
            template=template, section=section, slug="a", title="A",
            description="", offset_days=0, duration_days=1,
            role_key="admin", order=1,
        )
        t2 = ProdocTemplateTask.objects.create(
            template=template, section=section, slug="b", title="B",
            description="", offset_days=0, duration_days=1,
            role_key="admin", order=2,
        )
        with _flag_on():
            response = api_key_client.post(
                _deps_url(workspace.slug, template.id),
                data={"upstream": str(t1.id), "downstream": str(t2.id)},
                format="json",
            )
        assert response.status_code == status.HTTP_201_CREATED
