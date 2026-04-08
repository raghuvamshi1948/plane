# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""REST API tests for /api/v1/prodoc/.../holiday-calendars/."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.prodoc.models import HolidayCalendar


def _list_url(slug):
    return f"/api/v1/prodoc/workspaces/{slug}/holiday-calendars/"


def _detail_url(slug, pk):
    return f"/api/v1/prodoc/workspaces/{slug}/holiday-calendars/{pk}/"


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
class TestHolidayCalendarAPI:
    @pytest.mark.django_db
    def test_create_calendar_happy_path(self, api_key_client, workspace):
        with _flag_on():
            response = api_key_client.post(
                _list_url(workspace.slug),
                data={
                    "name": "India 2026",
                    "holidays": ["2026-08-15", "2026-01-26"],
                },
                format="json",
            )

        assert response.status_code == status.HTTP_201_CREATED
        # Serializer canonicalizes: sorted ascending.
        assert response.data["holidays"] == ["2026-01-26", "2026-08-15"]
        assert HolidayCalendar.objects.filter(
            workspace=workspace, name="India 2026"
        ).exists()

    @pytest.mark.django_db
    def test_list_calendars(self, api_key_client, workspace):
        HolidayCalendar.objects.create(
            workspace=workspace, name="A", holidays=[]
        )
        HolidayCalendar.objects.create(
            workspace=workspace, name="B", holidays=["2026-04-14"]
        )

        with _flag_on():
            response = api_key_client.get(_list_url(workspace.slug))

        assert response.status_code == status.HTTP_200_OK
        names = [row["name"] for row in response.data]
        assert names == ["A", "B"]

    @pytest.mark.django_db
    def test_retrieve_calendar(self, api_key_client, workspace):
        cal = HolidayCalendar.objects.create(
            workspace=workspace, name="Default", holidays=["2026-08-15"]
        )
        with _flag_on():
            response = api_key_client.get(_detail_url(workspace.slug, cal.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Default"
        assert response.data["holidays"] == ["2026-08-15"]

    @pytest.mark.django_db
    def test_patch_calendar(self, api_key_client, workspace):
        cal = HolidayCalendar.objects.create(
            workspace=workspace, name="Default", holidays=["2026-01-01"]
        )
        with _flag_on():
            response = api_key_client.patch(
                _detail_url(workspace.slug, cal.id),
                data={"holidays": ["2026-08-15", "2026-04-14"]},
                format="json",
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["holidays"] == ["2026-04-14", "2026-08-15"]
        cal.refresh_from_db()
        assert cal.holidays == ["2026-04-14", "2026-08-15"]

    @pytest.mark.django_db
    def test_delete_calendar_soft_deletes(self, api_key_client, workspace):
        cal = HolidayCalendar.objects.create(
            workspace=workspace, name="Default", holidays=[]
        )
        with _flag_on():
            response = api_key_client.delete(_detail_url(workspace.slug, cal.id))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        cal.refresh_from_db()
        assert cal.deleted_at is not None
        # Subsequent retrieve returns 404 — deleted rows are filtered out.
        with _flag_on():
            response = api_key_client.get(_detail_url(workspace.slug, cal.id))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.django_db
    def test_create_rejects_invalid_holiday_format(self, api_key_client, workspace):
        with _flag_on():
            response = api_key_client.post(
                _list_url(workspace.slug),
                data={"name": "Bad", "holidays": ["not-a-date"]},
                format="json",
            )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_create_rejects_duplicate_holidays(self, api_key_client, workspace):
        with _flag_on():
            response = api_key_client.post(
                _list_url(workspace.slug),
                data={"name": "Dup", "holidays": ["2026-08-15", "2026-08-15"]},
                format="json",
            )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_workspace_isolation(
        self, api_key_client, workspace, second_workspace
    ):
        # Create a calendar in workspace A.
        cal = HolidayCalendar.objects.create(
            workspace=workspace, name="WS-A Calendar", holidays=[]
        )

        # Workspace B's API key tries to read it via workspace B's URL.
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=second_workspace["token"].token)

        # B's list endpoint must not contain A's calendar.
        with _flag_on():
            response = client.get(_list_url(second_workspace["workspace"].slug))
        assert response.status_code == status.HTTP_200_OK
        names = [row["name"] for row in response.data]
        assert "WS-A Calendar" not in names

        # B's API key against A's URL must be denied (cross-tenant).
        with _flag_on():
            response = client.get(_detail_url(workspace.slug, cal.id))
        assert response.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )

    @pytest.mark.django_db
    def test_feature_flag_disabled_returns_404_on_list(
        self, api_key_client, workspace
    ):
        with _flag_off():
            response = api_key_client.get(_list_url(workspace.slug))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.django_db
    def test_feature_flag_disabled_returns_404_on_detail(
        self, api_key_client, workspace
    ):
        cal = HolidayCalendar.objects.create(
            workspace=workspace, name="X", holidays=[]
        )
        with _flag_off():
            response = api_key_client.get(_detail_url(workspace.slug, cal.id))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.django_db
    def test_detail_returns_404_for_unknown_id(self, api_key_client, workspace):
        with _flag_on():
            response = api_key_client.get(_detail_url(workspace.slug, uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND
