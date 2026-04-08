"""
Per-project Prodoc settings sidecar.

CLAUDE.md §2 forbids editing the upstream `Project` model
(`apps/api/plane/db/models/project.py`). When Prodoc needs project-scoped
configuration, it lives here as a OneToOne sidecar instead.

Today the only setting is `holiday_calendar`, an optional override that
overrides the workspace-default holiday calendar resolution for this
specific project. Future extensions can add more fields without
re-touching the upstream model.
"""

from django.db import models

from plane.db.models import BaseModel
from plane.prodoc.models.holiday import HolidayCalendar


class ProdocProjectSettings(BaseModel):
    project = models.OneToOneField(
        "db.Project",
        on_delete=models.CASCADE,
        related_name="prodoc_settings",
    )
    holiday_calendar = models.ForeignKey(
        HolidayCalendar,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="overriding_projects",
        help_text=(
            "Optional per-project override. If null, the cascade resolver "
            "falls back to the workspace's first HolidayCalendar by name."
        ),
    )

    class Meta:
        db_table = "prodoc_project_settings"
        verbose_name = "Prodoc Project Settings"
        verbose_name_plural = "Prodoc Project Settings"
