# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Tests for the dependency cascade signal handler."""

from datetime import date
from unittest.mock import patch

import pytest

from plane.db.models import Issue
from plane.prodoc.models import HolidayCalendar, ProdocProjectSettings


def _signal_flag_on():
    return patch(
        "plane.prodoc.signals.dependency.get_configuration_value",
        return_value=("1",),
    )


def _signal_flag_off():
    return patch(
        "plane.prodoc.signals.dependency.get_configuration_value",
        return_value=("0",),
    )


def _set_target(issue, target_date):
    """Save target_date in a context where the cascade signal is silent.

    Used to seed initial dates without triggering the cascade. Achieved
    by patching the flag off for the duration of the save.
    """
    with _signal_flag_off():
        issue.target_date = target_date
        issue.save(update_fields=["target_date"])


def _slip_target(issue, new_target_date):
    """Save target_date with the cascade flag enabled (the trigger)."""
    with _signal_flag_on():
        issue.target_date = new_target_date
        issue.save(update_fields=["target_date"])


@pytest.mark.contract
class TestCascade:
    @pytest.mark.django_db
    def test_cascade_fires_on_forward_slip(
        self, workspace, project, issue_factory, relation_factory
    ):
        a = issue_factory(project)
        b = issue_factory(project)
        # B is blocked by A.
        relation_factory(b, a, "blocked_by")
        _set_target(a, date(2026, 4, 13))  # Mon
        _set_target(b, date(2026, 4, 16))  # Thu

        # Slip A by 2 working days: Mon → Wed.
        _slip_target(a, date(2026, 4, 15))

        b.refresh_from_db()
        # B was Thu Apr 16 → +2 working days → Mon Apr 20 (skipping Sat/Sun).
        assert b.target_date == date(2026, 4, 20)

    @pytest.mark.django_db
    def test_cascade_no_op_on_backward_move(
        self, workspace, project, issue_factory, relation_factory
    ):
        """Slack absorbs backward moves (build plan §6.2)."""
        a = issue_factory(project)
        b = issue_factory(project)
        relation_factory(b, a, "blocked_by")
        _set_target(a, date(2026, 4, 15))
        _set_target(b, date(2026, 4, 20))

        # Pull A backward to Mon Apr 13.
        _slip_target(a, date(2026, 4, 13))

        b.refresh_from_db()
        # B unchanged.
        assert b.target_date == date(2026, 4, 20)

    @pytest.mark.django_db
    def test_cascade_respects_project_override_calendar(
        self, workspace, project, issue_factory, relation_factory
    ):
        # Workspace default has no holidays. Project override flags
        # Friday April 17 as a holiday.
        HolidayCalendar.objects.create(
            workspace=workspace, name="Default", holidays=[]
        )
        override = HolidayCalendar.objects.create(
            workspace=workspace, name="Override", holidays=["2026-04-17"]
        )
        ProdocProjectSettings.objects.create(
            project=project, holiday_calendar=override
        )

        a = issue_factory(project)
        b = issue_factory(project)
        relation_factory(b, a, "blocked_by")
        _set_target(a, date(2026, 4, 13))  # Mon
        _set_target(b, date(2026, 4, 16))  # Thu

        # Slip A by 1 working day. B's +1 from Thu Apr 16 should skip
        # Fri Apr 17 (override holiday) and Sat/Sun → Mon Apr 20.
        _slip_target(a, date(2026, 4, 14))

        b.refresh_from_db()
        assert b.target_date == date(2026, 4, 20)

    @pytest.mark.django_db
    def test_cascade_falls_back_to_workspace_calendar(
        self, workspace, project, issue_factory, relation_factory
    ):
        # Workspace default flags Fri April 17. No project override.
        HolidayCalendar.objects.create(
            workspace=workspace, name="Default", holidays=["2026-04-17"]
        )

        a = issue_factory(project)
        b = issue_factory(project)
        relation_factory(b, a, "blocked_by")
        _set_target(a, date(2026, 4, 13))
        _set_target(b, date(2026, 4, 16))

        _slip_target(a, date(2026, 4, 14))

        b.refresh_from_db()
        assert b.target_date == date(2026, 4, 20)

    @pytest.mark.django_db
    def test_cascade_is_idempotent(
        self, workspace, project, issue_factory, relation_factory
    ):
        a = issue_factory(project)
        b = issue_factory(project)
        relation_factory(b, a, "blocked_by")
        _set_target(a, date(2026, 4, 13))
        _set_target(b, date(2026, 4, 16))

        # First slip.
        _slip_target(a, date(2026, 4, 15))
        b.refresh_from_db()
        first = b.target_date

        # Re-saving A with the same target should produce no further movement.
        _slip_target(a, date(2026, 4, 15))
        b.refresh_from_db()
        assert b.target_date == first

    @pytest.mark.django_db
    def test_cascade_no_op_when_flag_disabled(
        self, workspace, project, issue_factory, relation_factory
    ):
        a = issue_factory(project)
        b = issue_factory(project)
        relation_factory(b, a, "blocked_by")
        _set_target(a, date(2026, 4, 13))
        _set_target(b, date(2026, 4, 16))

        # Cascade flag explicitly off.
        with _signal_flag_off():
            a.target_date = date(2026, 4, 15)
            a.save(update_fields=["target_date"])

        b.refresh_from_db()
        assert b.target_date == date(2026, 4, 16)

    @pytest.mark.django_db
    def test_cascade_skips_downstream_with_null_target_date(
        self, workspace, project, issue_factory, relation_factory
    ):
        """If a downstream has no target_date, cascade leaves it alone
        and does not fire a webhook for it (per the user's edit #5)."""
        a = issue_factory(project)
        b = issue_factory(project)
        relation_factory(b, a, "blocked_by")
        _set_target(a, date(2026, 4, 13))
        # B intentionally has no target_date.

        with _signal_flag_on(), patch(
            "plane.prodoc.signals.cascade.prodoc_dispatch_dependency_webhook"
        ) as mock_dispatch:
            a.target_date = date(2026, 4, 15)
            a.save(update_fields=["target_date"])

        b.refresh_from_db()
        assert b.target_date is None
        # No webhook fired for the null-target downstream.
        cascaded_calls = [
            c for c in mock_dispatch.delay.call_args_list
            if c.kwargs.get("action") == "cascaded"
        ]
        assert cascaded_calls == []

    @pytest.mark.django_db
    def test_cascade_fires_webhook_via_sidecar_optin(
        self, workspace, project, issue_factory, relation_factory, webhook_factory
    ):
        webhook_factory(workspace, issue=False, dependency_optin=True)

        a = issue_factory(project)
        b = issue_factory(project)
        relation_factory(b, a, "blocked_by")
        _set_target(a, date(2026, 4, 13))
        _set_target(b, date(2026, 4, 16))

        with _signal_flag_on(), patch(
            "plane.prodoc.signals.cascade.prodoc_dispatch_dependency_webhook"
        ) as mock_dispatch:
            a.target_date = date(2026, 4, 15)
            a.save(update_fields=["target_date"])

        cascaded = [
            c for c in mock_dispatch.delay.call_args_list
            if c.kwargs.get("action") == "cascaded"
        ]
        assert len(cascaded) == 1
        kwargs = cascaded[0].kwargs
        assert kwargs["issue_id"] == str(b.id)
        assert kwargs["related_issue_id"] == str(a.id)

    @pytest.mark.django_db
    def test_cascade_diamond_d_moves_exactly_once(
        self, workspace, project, issue_factory, relation_factory
    ):
        """A blocks B and C; both block D. A slips → D moves exactly once."""
        a = issue_factory(project)
        b = issue_factory(project)
        c = issue_factory(project)
        d = issue_factory(project)
        relation_factory(b, a, "blocked_by")
        relation_factory(c, a, "blocked_by")
        relation_factory(d, b, "blocked_by")
        relation_factory(d, c, "blocked_by")

        _set_target(a, date(2026, 4, 13))
        _set_target(b, date(2026, 4, 14))
        _set_target(c, date(2026, 4, 14))
        _set_target(d, date(2026, 4, 15))

        # Slip A by 1 working day.
        _slip_target(a, date(2026, 4, 14))

        d.refresh_from_db()
        # D should have moved from Apr 15 to Apr 16 (1 working day),
        # NOT Apr 17 (would happen if D were double-counted).
        assert d.target_date == date(2026, 4, 16)

    @pytest.mark.django_db
    def test_cascade_cycle_terminates_with_bounded_save_count(
        self, workspace, project, issue_factory, relation_factory
    ):
        """Cycle test: A blocked_by B, B blocked_by A. The cascade must
        terminate. Save-count assertion bounds total Issue.save() calls
        at 2 * len(cycle); for a 2-node cycle that's <= 4 saves total."""
        a = issue_factory(project)
        b = issue_factory(project)
        relation_factory(a, b, "blocked_by")  # A blocked_by B
        relation_factory(b, a, "blocked_by")  # B blocked_by A
        _set_target(a, date(2026, 4, 13))
        _set_target(b, date(2026, 4, 16))

        save_calls = []
        original_save = Issue.save

        def counting_save(self, *args, **kwargs):
            save_calls.append(self.id)
            return original_save(self, *args, **kwargs)

        with patch.object(Issue, "save", counting_save), _signal_flag_on():
            a.target_date = date(2026, 4, 15)
            a.save(update_fields=["target_date"])

        # 2 * len(cycle) = 4. Total saves should be at most 4: the user's
        # save on A, plus B's cascade save. The cycle back to A is
        # terminated by the visited set in the walker.
        assert len(save_calls) <= 4
        assert len(save_calls) >= 2  # at least the user's save + B's cascade
