"""
Calendar resolution for the Extension 2 cascade.

The cascade signal handler asks "what holidays apply to this project?"
and gets back either a `HolidayCalendar` instance or `None`. The lookup
order is:

    1. ProdocProjectSettings.holiday_calendar  (project-level override)
    2. Workspace's first HolidayCalendar, ordered by name (default)
    3. None  (caller treats as 'no holidays, weekends only')

`None` is a perfectly valid result — it just means business-day
arithmetic will skip weekends but no named holidays for this project.
"""

from datetime import date

from plane.prodoc.models import HolidayCalendar, ProdocProjectSettings


def resolve_calendar_for_project(project_id, workspace_id):
    """Return the resolved HolidayCalendar for a project, or None.

    Both IDs are required so the workspace fallback can be served
    without an extra Project lookup. Callers (the cascade signal) almost
    always have both already in hand from the issue instance.
    """
    settings = (
        ProdocProjectSettings.objects.filter(
            project_id=project_id,
            deleted_at__isnull=True,
            holiday_calendar__isnull=False,
        )
        .select_related("holiday_calendar")
        .first()
    )
    if settings is not None:
        return settings.holiday_calendar

    return (
        HolidayCalendar.objects.filter(
            workspace_id=workspace_id,
            deleted_at__isnull=True,
        )
        .order_by("name")
        .first()
    )


def parse_holidays(json_list):
    """Convert a HolidayCalendar.holidays JSON list to a set[date].

    Used by the cascade hot path. Invalid dates are silently skipped so
    a malformed entry never crashes a cascade run; the validation
    contract lives in HolidayCalendarSerializer at write time.
    """
    out = set()
    if not json_list:
        return out
    for entry in json_list:
        try:
            out.add(date.fromisoformat(entry))
        except (TypeError, ValueError):
            continue
    return out
