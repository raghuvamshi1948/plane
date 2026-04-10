# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""REST API tests for sites and waves.

Covers CRUD happy paths for sites and waves, wave→module mirror
creation on POST (build plan §7.2), wave-site attach/detach, workspace
isolation, and feature-flag 404.
"""

from unittest.mock import patch

import pytest
from rest_framework import status

from plane.db.models import Module
from plane.prodoc.models import ProdocSite, ProdocWave, ProdocWaveSite


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


def _sites_url(slug, project_id):
    return f"/api/v1/prodoc/workspaces/{slug}/projects/{project_id}/sites/"


def _site_url(slug, project_id, site_id):
    return (
        f"/api/v1/prodoc/workspaces/{slug}/projects/{project_id}"
        f"/sites/{site_id}/"
    )


def _waves_url(slug, project_id):
    return f"/api/v1/prodoc/workspaces/{slug}/projects/{project_id}/waves/"


def _wave_url(slug, project_id, wave_id):
    return (
        f"/api/v1/prodoc/workspaces/{slug}/projects/{project_id}"
        f"/waves/{wave_id}/"
    )


def _wave_sites_url(slug, project_id, wave_id):
    return (
        f"/api/v1/prodoc/workspaces/{slug}/projects/{project_id}"
        f"/waves/{wave_id}/sites/"
    )


def _wave_site_url(slug, project_id, wave_id, site_id):
    return (
        f"/api/v1/prodoc/workspaces/{slug}/projects/{project_id}"
        f"/waves/{wave_id}/sites/{site_id}/"
    )


@pytest.mark.contract
class TestProdocSiteAPI:
    @pytest.mark.django_db
    def test_create_and_list_site(self, api_key_client, workspace, project):
        with _flag_on():
            response = api_key_client.post(
                _sites_url(workspace.slug, project.id),
                data={"name": "Hospital A", "code": "HOSP-A"},
                format="json",
            )
        assert response.status_code == status.HTTP_201_CREATED

        with _flag_on():
            response = api_key_client.get(
                _sites_url(workspace.slug, project.id)
            )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["code"] == "HOSP-A"

    @pytest.mark.django_db
    def test_patch_site(self, api_key_client, workspace, project):
        site = ProdocSite.objects.create(
            workspace=workspace, project=project, name="X", code="X1"
        )
        with _flag_on():
            response = api_key_client.patch(
                _site_url(workspace.slug, project.id, site.id),
                data={"name": "X Updated"},
                format="json",
            )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "X Updated"

    @pytest.mark.django_db
    def test_delete_site_soft_deletes(
        self, api_key_client, workspace, project
    ):
        site = ProdocSite.objects.create(
            workspace=workspace, project=project, name="X", code="X1"
        )
        with _flag_on():
            response = api_key_client.delete(
                _site_url(workspace.slug, project.id, site.id)
            )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        site.refresh_from_db()
        assert site.deleted_at is not None

    @pytest.mark.django_db
    def test_feature_flag_disabled_returns_404(
        self, api_key_client, workspace, project
    ):
        with _flag_off():
            response = api_key_client.get(
                _sites_url(workspace.slug, project.id)
            )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.django_db
    def test_workspace_isolation(
        self, api_key_client, workspace, project, second_workspace
    ):
        ProdocSite.objects.create(
            workspace=second_workspace["workspace"],
            project=second_workspace["project"],
            name="Foreign",
            code="FOR",
        )
        with _flag_on():
            response = api_key_client.get(
                _sites_url(workspace.slug, project.id)
            )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0


@pytest.mark.contract
class TestProdocWaveAPI:
    @pytest.mark.django_db
    def test_create_wave_also_creates_plane_module(
        self, api_key_client, workspace, project
    ):
        module_count_before = Module.objects.filter(project=project).count()
        with _flag_on():
            response = api_key_client.post(
                _waves_url(workspace.slug, project.id),
                data={"name": "Wave 1", "order": 1, "start_offset_days": 0},
                format="json",
            )
        assert response.status_code == status.HTTP_201_CREATED
        # The wave row was created.
        wave_id = response.data["id"]
        wave = ProdocWave.objects.get(id=wave_id)
        # And the Module mirror in the same atomic block.
        assert wave.plane_module is not None
        assert wave.plane_module.name == "Wave 1"
        assert (
            Module.objects.filter(project=project).count()
            == module_count_before + 1
        )

    @pytest.mark.django_db
    def test_delete_wave_leaves_module_intact(
        self, api_key_client, workspace, project
    ):
        module = Module.objects.create(
            name="Wave A", project=project, workspace=workspace
        )
        wave = ProdocWave.objects.create(
            workspace=workspace,
            project=project,
            name="Wave A",
            order=1,
            plane_module=module,
        )
        with _flag_on():
            response = api_key_client.delete(
                _wave_url(workspace.slug, project.id, wave.id)
            )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        wave.refresh_from_db()
        assert wave.deleted_at is not None
        # Module survives — SET_NULL behavior on plane_module FK.
        assert Module.objects.filter(id=module.id).exists()

    @pytest.mark.django_db
    def test_list_waves_ordered(self, api_key_client, workspace, project):
        for i, name in enumerate(["B", "A"], start=1):
            m = Module.objects.create(
                name=name, project=project, workspace=workspace
            )
            ProdocWave.objects.create(
                workspace=workspace,
                project=project,
                name=name,
                order=i,
                plane_module=m,
            )
        with _flag_on():
            response = api_key_client.get(
                _waves_url(workspace.slug, project.id)
            )
        assert response.status_code == status.HTTP_200_OK
        assert [row["order"] for row in response.data] == [1, 2]


@pytest.mark.contract
class TestProdocWaveSiteAttachAPI:
    @pytest.mark.django_db
    def test_attach_and_detach_site(
        self, api_key_client, workspace, project
    ):
        module = Module.objects.create(
            name="W", project=project, workspace=workspace
        )
        wave = ProdocWave.objects.create(
            workspace=workspace,
            project=project,
            name="W",
            order=1,
            plane_module=module,
        )
        site = ProdocSite.objects.create(
            workspace=workspace, project=project, name="S", code="S1"
        )
        with _flag_on():
            response = api_key_client.post(
                _wave_sites_url(workspace.slug, project.id, wave.id),
                data={"site": str(site.id)},
                format="json",
            )
        assert response.status_code == status.HTTP_201_CREATED
        assert ProdocWaveSite.objects.filter(
            wave=wave, site=site, deleted_at__isnull=True
        ).exists()

        # Idempotent attach returns 200.
        with _flag_on():
            response = api_key_client.post(
                _wave_sites_url(workspace.slug, project.id, wave.id),
                data={"site": str(site.id)},
                format="json",
            )
        assert response.status_code == status.HTTP_200_OK

        with _flag_on():
            response = api_key_client.delete(
                _wave_site_url(
                    workspace.slug, project.id, wave.id, site.id
                )
            )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        # Default manager filters soft-deleted rows; use all_objects.
        rel = ProdocWaveSite.all_objects.get(wave=wave, site=site)
        assert rel.deleted_at is not None
