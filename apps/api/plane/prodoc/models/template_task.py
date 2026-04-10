"""
Reusable task blueprint within a ProdocTemplate.

A `ProdocTemplateTask` is a single unit of work (e.g. "Provision user
accounts", "Wave go-live readiness review") parameterized by offset,
duration, role, expansion flags, and SLA. At materialization time
(commit 5) the materializer walks the task list, expands each task
against the project's Sites and Waves per the `repeat_per_*` flags,
computes dates via Ext 2's `add_business_days`, and creates a concrete
Plane `Issue` row for every expansion.

Identity within a template is `(template, slug)` — the slug is the
durable handle template authors reference in the seed JSON. The brief's
C1 resolution (see plan file) picked JSONField list of slugs for
`migration_requirement_slugs` and `third_party_tool_slugs` over a typed
M2M: templates stay portable as a single JSON document, and the
materializer validates slug resolution at build-plan time.

`ProdocTemplateTaskDependency` is the upstream→downstream edge. Identity
is `(upstream, downstream)`; a CHECK constraint forbids self-edges.
Cycles are the serializer's responsibility (commit 8), not the DB —
the graph has to tolerate staged template edits that temporarily look
cyclic during a multi-step API call.
"""

from django.db import models

from plane.db.models import BaseModel

from .template import ProdocTemplate, ProdocTemplateSection


class ProdocTemplateTask(BaseModel):
    DEPENDENCY_MODE_CHOICES = (
        ("all", "all"),
        ("same_site", "same_site"),
    )

    template = models.ForeignKey(
        ProdocTemplate,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    section = models.ForeignKey(
        ProdocTemplateSection,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    slug = models.SlugField(max_length=120)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    offset_days = models.IntegerField(
        help_text="Working-day offset from the project start date.",
    )
    duration_days = models.IntegerField(
        help_text="Working-day duration of the task.",
    )
    role_key = models.CharField(max_length=50)
    sla_hours = models.IntegerField(null=True, blank=True)
    repeat_per_site = models.BooleanField(default=False)
    repeat_per_wave = models.BooleanField(default=False)
    dependency_mode = models.CharField(
        max_length=20,
        default="all",
        choices=DEPENDENCY_MODE_CHOICES,
    )
    order = models.IntegerField()
    migration_requirement_slugs = models.JSONField(
        default=list,
        help_text=(
            "List of ProdocMigrationRequirement slugs (workspace-scoped) to "
            "link to the materialized work items. Validated at materialize "
            "time against the workspace's requirement catalog."
        ),
    )
    third_party_tool_slugs = models.JSONField(
        default=list,
        help_text=(
            "List of ProdocThirdPartyTool slugs (workspace-scoped) to link "
            "to the materialized work items."
        ),
    )

    class Meta:
        db_table = "prodoc_template_tasks"
        verbose_name = "Prodoc Template Task"
        verbose_name_plural = "Prodoc Template Tasks"
        unique_together = [("template", "slug")]
        ordering = ["order"]
        indexes = [
            models.Index(fields=["template", "order"]),
        ]

    def __str__(self):
        return f"{self.template.slug}/{self.slug}"


class ProdocTemplateTaskDependency(BaseModel):
    upstream = models.ForeignKey(
        ProdocTemplateTask,
        on_delete=models.CASCADE,
        related_name="downstream_deps",
    )
    downstream = models.ForeignKey(
        ProdocTemplateTask,
        on_delete=models.CASCADE,
        related_name="upstream_deps",
    )

    class Meta:
        db_table = "prodoc_template_task_dependencies"
        verbose_name = "Prodoc Template Task Dependency"
        verbose_name_plural = "Prodoc Template Task Dependencies"
        unique_together = [("upstream", "downstream")]
        constraints = [
            models.CheckConstraint(
                check=~models.Q(upstream=models.F("downstream")),
                name="prodoc_tpl_task_dep_no_self",
            ),
        ]

    def __str__(self):
        return f"{self.upstream_id} -> {self.downstream_id}"
