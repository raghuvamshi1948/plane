# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Tests for HolidayCalendar, ProdocProjectSettings, and the calendar
resolver helper. These are model-layer tests, not endpoint tests."""

import pytest

from plane.prodoc.models import HolidayCalendar, ProdocProjectSettings
from plane.prodoc.scheduling.calendar_resolver import (
    parse_holidays,
    resolve_calendar_for_project,
)


@pytest.mark.contract
class TestCalendarResolver:
    @pytest.mark.django_db
    def test_workspace_isolation_calendar_invisible_to_other_workspace(
        self, workspace, project, second_workspace
    ):
        # Create a calendar in workspace A.
        HolidayCalendar.objects.create(
            workspace=workspace,
            name="India 2026",
            holidays=["2026-04-14"],
        )

        # Resolver scoped to workspace B should not see it.
        result = resolve_calendar_for_project(
            project_id=second_workspace["project"].id,
            workspace_id=second_workspace["workspace"].id,
        )
        assert result is None

    @pytest.mark.django_db
    def test_resolver_returns_project_override_when_set(
        self, workspace, project
    ):
        default_cal = HolidayCalendar.objects.create(
            workspace=workspace, name="Default", holidays=["2026-04-14"]
        )
        override_cal = HolidayCalendar.objects.create(
            workspace=workspace, name="Override", holidays=["2026-08-15"]
        )
        ProdocProjectSettings.objects.create(
            project=project, holiday_calendar=override_cal
        )

        result = resolve_calendar_for_project(
            project_id=project.id, workspace_id=workspace.id
        )
        assert result.id == override_cal.id

    @pytest.mark.django_db
    def test_resolver_falls_back_to_workspace_default_when_no_override(
        self, workspace, project
    ):
        default_cal = HolidayCalendar.objects.create(
            workspace=workspace, name="A-Default", holidays=["2026-04-14"]
        )
        # Second calendar with later name; resolver should pick A-Default.
        HolidayCalendar.objects.create(
            workspace=workspace, name="Z-Other", holidays=["2026-08-15"]
        )

        result = resolve_calendar_for_project(
            project_id=project.id, workspace_id=workspace.id
        )
        assert result.id == default_cal.id

    @pytest.mark.django_db
    def test_resolver_returns_none_when_no_calendars_exist(
        self, workspace, project
    ):
        result = resolve_calendar_for_project(
            project_id=project.id, workspace_id=workspace.id
        )
        assert result is None

    @pytest.mark.django_db
    def test_resolver_falls_back_when_override_setting_has_null_calendar(
        self, workspace, project
    ):
        default_cal = HolidayCalendar.objects.create(
            workspace=workspace, name="Default", holidays=["2026-04-14"]
        )
        # Settings row exists but holiday_calendar is null — should NOT
        # block the workspace fallback.
        ProdocProjectSettings.objects.create(project=project, holiday_calendar=None)

        result = resolve_calendar_for_project(
            project_id=project.id, workspace_id=workspace.id
        )
        assert result.id == default_cal.id


class TestParseHolidays:
    def test_empty_input_returns_empty_set(self):
        assert parse_holidays(None) == set()
        assert parse_holidays([]) == set()

    def test_valid_iso_strings_parsed(self):
        from datetime import date

        result = parse_holidays(["2026-04-14", "2026-08-15"])
        assert result == {date(2026, 4, 14), date(2026, 8, 15)}

    def test_invalid_entries_skipped(self):
        from datetime import date

        result = parse_holidays(["2026-04-14", "not-a-date", None, 42])
        assert result == {date(2026, 4, 14)}
