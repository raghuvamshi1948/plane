"""
Workspace-scoped Prodoc project templates.

A `ProdocTemplate` describes a reusable implementation playbook (e.g. a
healthcare-provider onboarding) as an ordered set of `ProdocTemplateSection`
groups, each containing `ProdocTemplateTask` rows (commit 2). At
materialization time (commit 5+) the template is expanded against per-project
Sites and Waves into concrete Plane work items.

Identity is `(workspace, slug, version)` — the slug is the durable handle
the seed command and API consumers reference; humans pick the version
explicitly. Once a template has been used to materialize a project,
`is_locked` is flipped to True and further edits require bumping
`version` and creating a new row. This avoids the "edit a template
that's already in production" footgun documented in build plan §7.2.

Workspace tenant isolation per CLAUDE.md §3 — every queryset filters
through `workspace_id` (or `template__workspace_id` for child rows).
"""

from django.db import models

from plane.db.models import BaseModel, Workspace


class ProdocTemplate(BaseModel):
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="prodoc_templates",
    )
    slug = models.SlugField(max_length=120)
    version = models.CharField(max_length=20)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_locked = models.BooleanField(
        default=False,
        help_text=(
            "Set True automatically on the first successful materialization. "
            "Locked templates reject PATCH; bump `version` to create a new row."
        ),
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "prodoc_templates"
        verbose_name = "Prodoc Template"
        verbose_name_plural = "Prodoc Templates"
        unique_together = [("workspace", "slug", "version")]
        indexes = [
            models.Index(fields=["workspace", "slug"]),
        ]

    def __str__(self):
        return f"{self.slug}@{self.version} ({self.workspace.slug})"


class ProdocTemplateSection(BaseModel):
    template = models.ForeignKey(
        ProdocTemplate,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    name = models.CharField(max_length=200)
    order = models.IntegerField()

    class Meta:
        db_table = "prodoc_template_sections"
        verbose_name = "Prodoc Template Section"
        verbose_name_plural = "Prodoc Template Sections"
        unique_together = [("template", "order")]
        ordering = ["order"]

    def __str__(self):
        return f"{self.template.slug}#{self.order} {self.name}"
