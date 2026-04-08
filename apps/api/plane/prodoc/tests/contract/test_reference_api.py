# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""REST API tests for /api/v1/prodoc/.../migration-requirements/
and /api/v1/prodoc/.../third-party-tools/."""

from unittest.mock import patch

import pytest
from rest_framework import status

from plane.prodoc.models import ProdocMigrationRequirement, ProdocThirdPartyTool


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


def _req_list_url(slug):
    return f"/api/v1/prodoc/workspaces/{slug}/migration-requirements/"


def _tool_list_url(slug):
    return f"/api/v1/prodoc/workspaces/{slug}/third-party-tools/"


@pytest.mark.contract
class TestReferenceAPI:
    @pytest.mark.django_db
    def test_create_and_list_migration_requirement(
        self, api_key_client, workspace
    ):
        with _flag_on():
            response = api_key_client.post(
                _req_list_url(workspace.slug),
                data={
                    "slug": "req-export",
                    "name": "Export",
                    "category": "data",
                    "default_owner_role": "admin",
                },
                format="json",
            )
        assert response.status_code == status.HTTP_201_CREATED

        with _flag_on():
            response = api_key_client.get(_req_list_url(workspace.slug))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["slug"] == "req-export"

    @pytest.mark.django_db
    def test_create_third_party_tool(self, api_key_client, workspace):
        with _flag_on():
            response = api_key_client.post(
                _tool_list_url(workspace.slug),
                data={
                    "slug": "tool-salesforce",
                    "name": "Salesforce",
                    "category": "crm",
                    "default_owner_role": "admin",
                },
                format="json",
            )
        assert response.status_code == status.HTTP_201_CREATED

    @pytest.mark.django_db
    def test_feature_flag_disabled_returns_404(
        self, api_key_client, workspace
    ):
        with _flag_off():
            response = api_key_client.get(_req_list_url(workspace.slug))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.django_db
    def test_workspace_isolation(
        self, api_key_client, workspace, second_workspace
    ):
        ProdocMigrationRequirement.objects.create(
            workspace=second_workspace["workspace"],
            slug="req-foreign",
            name="Foreign",
            category="data",
            default_owner_role="admin",
        )
        with _flag_on():
            response = api_key_client.get(_req_list_url(workspace.slug))
        assert response.status_code == status.HTTP_200_OK
        slugs = [row["slug"] for row in response.data]
        assert "req-foreign" not in slugs
