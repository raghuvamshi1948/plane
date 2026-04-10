"""
Per-project Waves for the Prodoc materialization engine.

A `ProdocWave` is a rollout cohort that bundles one or more
`ProdocSite`s. At materialization time, any `ProdocTemplateTask` with
`repeat_per_wave=True` expands once per Wave; combined with
`repeat_per_site=True` it expands per (Wave, Site) pair where the Site
is a member of the Wave.

Each Wave mirrors to a native Plane `Module` of the same name so ops
can use Plane's native Module view for burndown and filtering. The
mirror Module is created when the wave is POSTed (commit 9). The FK
is `SET_NULL` on Module delete so historical data survives — if a
Module is removed through Plane's own surface, the Wave still
references the historical work-item set.

`workspace` is denormalized per CLAUDE.md §3.
`start_offset_days` is measured in working days from the project's
start date; it shifts every task in the wave forward.
"""

from django.db import models

from plane.db.models import BaseModel, Workspace

from .site import ProdocSite


class ProdocWave(BaseModel):
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="prodoc_waves",
    )
    project = models.ForeignKey(
        "db.Project",
        on_delete=models.CASCADE,
        related_name="prodoc_waves",
    )
    name = models.CharField(max_length=200)
    order = models.IntegerField()
    start_offset_days = models.IntegerField(default=0)
    plane_module = models.ForeignKey(
        "db.Module",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text=(
            "Mirror Plane Module for this wave. Created by the wave POST "
            "endpoint (commit 9). SET_NULL on Module delete so the Wave "
            "row survives upstream Module lifecycle changes."
        ),
    )

    class Meta:
        db_table = "prodoc_waves"
        verbose_name = "Prodoc Wave"
        verbose_name_plural = "Prodoc Waves"
        unique_together = [("project", "name"), ("project", "order")]
        ordering = ["order"]
        indexes = [
            models.Index(fields=["workspace", "project"]),
        ]

    def __str__(self):
        return f"{self.name} (#{self.order})"


class ProdocWaveSite(BaseModel):
    wave = models.ForeignKey(
        ProdocWave,
        on_delete=models.CASCADE,
        related_name="wave_sites",
    )
    site = models.ForeignKey(
        ProdocSite,
        on_delete=models.CASCADE,
        related_name="site_waves",
    )

    class Meta:
        db_table = "prodoc_wave_sites"
        verbose_name = "Prodoc Wave Site"
        verbose_name_plural = "Prodoc Wave Sites"
        unique_together = [("wave", "site")]

    def __str__(self):
        return f"{self.wave_id}::{self.site_id}"
