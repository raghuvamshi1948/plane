"""
Post-mortem record for a template materialization run.

Every call to `POST /api/v1/prodoc/projects/<id>/materialize/` in
wet-run mode creates one of these rows *before* the Celery task fires.
The task walks it through the `queued → running → succeeded|failed`
state machine and appends the ids of every row it created to the
three JSONField lists — `work_items_created`, `modules_created`,
`relations_created`. On failure the Celery task's rollback pass
(commit 7) walks those lists to soft-delete anything that landed on
disk before the error.

Why three separate JSON lists instead of a single `artifacts` list:
the rollback pass needs to know *which model* to soft-delete, and
storing the ids by model type keeps the rollback loop trivially
iterable per model without a discriminator column.

Why `on_delete=PROTECT` on `template`: losing a template while a job
row still points at it would orphan the post-mortem. Ops deletes
templates only after every job referencing them has been archived.

Why `error_log` is a TextField and not JSON: ops reads it once, with
a human eyeball, on a failure. A traceback + a couple of warning
lines is cheaper to grep as plain text than to slice as structured
JSON.
"""

from django.db import models

from plane.db.models import BaseModel, Project, Workspace

from .template import ProdocTemplate


class ProdocMaterializationJob(BaseModel):
    STATUS_CHOICES = (
        ("queued", "Queued"),
        ("running", "Running"),
        ("succeeded", "Succeeded"),
        ("failed", "Failed"),
    )

    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="prodoc_materialization_jobs",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="prodoc_materialization_jobs",
    )
    template = models.ForeignKey(
        ProdocTemplate,
        on_delete=models.PROTECT,
        related_name="materialization_jobs",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="queued"
    )
    start_date = models.DateField()
    error_log = models.TextField(blank=True, default="")
    work_items_created = models.JSONField(default=list)
    modules_created = models.JSONField(default=list)
    relations_created = models.JSONField(default=list)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "prodoc_materialization_jobs"
        verbose_name = "Prodoc Materialization Job"
        verbose_name_plural = "Prodoc Materialization Jobs"
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["workspace", "status"]),
        ]
        ordering = ("-created_at",)

    def __str__(self):
        return f"job<{self.id}> {self.template.slug}@{self.template.version} ({self.status})"
