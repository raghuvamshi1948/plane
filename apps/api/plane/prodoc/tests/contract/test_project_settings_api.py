# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""REST API tests for /api/v1/prodoc/.../projects/<id>/settings/."""

from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.prodoc.models import HolidayCalendar, ProdocProjectSettings


def _url(slug, project_id):
    return f"/api/v1/prodoc/workspaces/{slug}/projects/{project_id}/settings/"


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


@pytest.mark.contract
class TestProdocProjectSettingsAPI:
    @pytest.mark.django_db
    def test_get_returns_empty_when_no_row_yet(
        self, api_key_client, workspace, project
    ):
        with _flag_on():
            response = api_key_client.get(_url(workspace.slug, project.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["holiday_calendar"] is None
        assert response.data["project"] == str(project.id)
        # No row was auto-created by GET.
        assert not ProdocProjectSettings.objects.filter(project=project).exists()

    @pytest.mark.django_db
    def test_patch_creates_row_on_first_write(
        self, api_key_client, workspace, project
    ):
        cal = HolidayCalendar.objects.create(
            workspace=workspace, name="Default", holidays=[]
        )

        with _flag_on():
            response = api_key_client.patch(
                _url(workspace.slug, project.id),
                data={"holiday_calendar": str(cal.id)},
                format="json",
            )

        assert response.status_code == status.HTTP_201_CREATED
        settings = ProdocProjectSettings.objects.get(project=project)
        assert settings.holiday_calendar_id == cal.id

    @pytest.mark.django_db
    def test_patch_updates_existing_row(
        self, api_key_client, workspace, project
    ):
        old_cal = HolidayCalendar.objects.create(
            workspace=workspace, name="Old", holidays=[]
        )
        new_cal = HolidayCalendar.objects.create(
            workspace=workspace, name="New", holidays=[]
        )
        ProdocProjectSettings.objects.create(
            project=project, holiday_calendar=old_cal
        )

        with _flag_on():
            response = api_key_client.patch(
                _url(workspace.slug, project.id),
                data={"holiday_calendar": str(new_cal.id)},
                format="json",
            )

        assert response.status_code == status.HTTP_200_OK
        settings = ProdocProjectSettings.objects.get(project=project)
        assert settings.holiday_calendar_id == new_cal.id

    @pytest.mark.django_db
    def test_patch_can_clear_override(
        self, api_key_client, workspace, project
    ):
        cal = HolidayCalendar.objects.create(
            workspace=workspace, name="C", holidays=[]
        )
        ProdocProjectSettings.objects.create(project=project, holiday_calendar=cal)

        with _flag_on():
            response = api_key_client.patch(
                _url(workspace.slug, project.id),
                data={"holiday_calendar": None},
                format="json",
            )

        assert response.status_code == status.HTTP_200_OK
        settings = ProdocProjectSettings.objects.get(project=project)
        assert settings.holiday_calendar is None

    @pytest.mark.django_db
    def test_patch_rejects_calendar_from_other_workspace(
        self, api_key_client, workspace, project, second_workspace
    ):
        # Create the calendar in workspace B but try to set it on a
        # project in workspace A. The serializer must reject.
        foreign_cal = HolidayCalendar.objects.create(
            workspace=second_workspace["workspace"],
            name="Foreign",
            holidays=[],
        )

        with _flag_on():
            response = api_key_client.patch(
                _url(workspace.slug, project.id),
                data={"holiday_calendar": str(foreign_cal.id)},
                format="json",
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not ProdocProjectSettings.objects.filter(project=project).exists()

    @pytest.mark.django_db
    def test_get_returns_existing_row(
        self, api_key_client, workspace, project
    ):
        cal = HolidayCalendar.objects.create(
            workspace=workspace, name="X", holidays=["2026-08-15"]
        )
        ProdocProjectSettings.objects.create(project=project, holiday_calendar=cal)

        with _flag_on():
            response = api_key_client.get(_url(workspace.slug, project.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["holiday_calendar"] == cal.id

    @pytest.mark.django_db
    def test_workspace_isolation_cross_tenant(
        self, workspace, project, second_workspace
    ):
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=second_workspace["token"].token)

        # B's API key against A's URL must not be allowed to mutate.
        with _flag_on():
            response = client.patch(
                _url(workspace.slug, project.id),
                data={"holiday_calendar": None},
                format="json",
            )
        assert response.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )
        assert not ProdocProjectSettings.objects.filter(project=project).exists()

    @pytest.mark.django_db
    def test_feature_flag_disabled_returns_404(
        self, api_key_client, workspace, project
    ):
        with _flag_off():
            response = api_key_client.get(_url(workspace.slug, project.id))
        assert response.status_code == status.HTTP_404_NOT_FOUND
