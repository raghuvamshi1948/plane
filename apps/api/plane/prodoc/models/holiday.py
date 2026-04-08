"""
Workspace-scoped holiday calendars for the Extension 2 business-day
scheduler.

Design notes:

- Holidays are stored as a JSON list of ISO date strings (`["2026-04-14",
  "2026-08-15", ...]`) on the calendar row, not as a related
  `HolidayDate` table. The §6.4 build plan suggested a relational model
  with `(workspace, date)` unique constraints; we deviate because:

  1. Holiday lists are read-mostly and small (typically ≤ 30 entries
     per year per region).
  2. The cascade hot path needs the full set in memory anyway — every
     `add_business_days` call walks the holidays as a `set` for O(1)
     lookup. Joining a related table per call would be slower, not
     faster.
  3. Avoids a second model and migration in this commit.
  4. Keeps the pure `add_business_days` utility (Ext 2 commit 4) trivially
     unit-testable with a plain Python list — no Django imports.

  Validation that the JSON is a sorted list of ISO date strings without
  duplicates lives in `HolidayCalendarSerializer`, not in the model
  layer, since the model is also written from migrations and management
  commands.
"""

from django.db import models

from plane.db.models import BaseModel, Workspace


class HolidayCalendar(BaseModel):
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="prodoc_holiday_calendars",
    )
    name = models.CharField(max_length=200)
    holidays = models.JSONField(
        default=list,
        help_text="List of ISO date strings, e.g. ['2026-04-14', '2026-08-15'].",
    )

    class Meta:
        db_table = "prodoc_holiday_calendars"
        verbose_name = "Prodoc Holiday Calendar"
        verbose_name_plural = "Prodoc Holiday Calendars"
        unique_together = [("workspace", "name")]
        indexes = [models.Index(fields=["workspace"])]

    def __str__(self):
        return f"{self.name} ({self.workspace.slug})"
