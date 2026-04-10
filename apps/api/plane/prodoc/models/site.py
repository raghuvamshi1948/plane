"""
Per-project Sites for the Prodoc materialization engine.

A `ProdocSite` represents an independent customer user team (for
healthcare ops, typically an individual hospital within a health-system
engagement). Sites are scoped per project per the build plan §7.1
decision — "Sites belong to Project, not persistent-per-customer" — so
the data model stays small. Cross-project Site reporting can be added
later via a nullable `organization_site_id` upgrade without breaking
the materializer contract.

At materialization time, any `ProdocTemplateTask` with
`repeat_per_site=True` gets expanded once per Site.

`workspace` is denormalized (kept in sync with `project.workspace`) so
tenant-scoped queries don't have to join through `Project`. CLAUDE.md §3
requires every Prodoc model to carry a workspace FK or a project FK;
this one carries both.
"""

from django.db import models

from plane.db.models import BaseModel, Workspace


class ProdocSite(BaseModel):
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="prodoc_sites",
    )
    project = models.ForeignKey(
        "db.Project",
        on_delete=models.CASCADE,
        related_name="prodoc_sites",
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "prodoc_sites"
        verbose_name = "Prodoc Site"
        verbose_name_plural = "Prodoc Sites"
        unique_together = [("project", "code")]
        indexes = [
            models.Index(fields=["workspace", "project"]),
        ]

    def __str__(self):
        return f"{self.code} ({self.name})"
