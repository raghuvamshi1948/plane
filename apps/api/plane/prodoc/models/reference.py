"""
Workspace-scoped reference catalogs for migration requirements and
third-party tools.

Template tasks reference these rows by slug (C1 decision — see Ext 3
plan file) via the `migration_requirement_slugs` and `third_party_tool_slugs`
JSONField lists on `ProdocTemplateTask`. At materialize time (commit 5)
the engine resolves each slug against the project's workspace catalog
and raises a `MaterializationValidationError` listing any unresolved
slug before writing a single work item.

Why a slug field at all (C4 gap resolution — see Ext 3 plan file): the
seed command is idempotent by `(workspace, slug)`, and templates need
a stable identifier across versions and workspaces that survives
rename. Without a slug, template JSON would break every time a
requirement's display name changes.

Both models share the same shape; they exist as separate tables
rather than a single polymorphic `ReferenceItem` because (a) ops
filters them separately in the UI, (b) their category enums differ
from each other in later extensions, (c) one table per concept is
the idiomatic Django pattern.
"""

from django.db import models

from plane.db.models import BaseModel, Workspace


REQUIREMENT_CATEGORY_CHOICES = (
    ("data", "Data Migration"),
    ("access", "Access Provisioning"),
    ("compliance", "Compliance / Legal"),
    ("integration", "System Integration"),
    ("other", "Other"),
)


TOOL_CATEGORY_CHOICES = (
    ("crm", "CRM"),
    ("analytics", "Analytics"),
    ("communication", "Communication"),
    ("security", "Security"),
    ("other", "Other"),
)


class ProdocMigrationRequirement(BaseModel):
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="prodoc_migration_requirements",
    )
    slug = models.SlugField(
        max_length=120,
        help_text=(
            "Stable workspace-scoped handle referenced from template task "
            "`migration_requirement_slugs` JSON lists. Required; the seed "
            "command and materializer both resolve by slug."
        ),
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=40, choices=REQUIREMENT_CATEGORY_CHOICES, default="other"
    )
    default_owner_role = models.CharField(max_length=50)

    class Meta:
        db_table = "prodoc_migration_requirements"
        verbose_name = "Prodoc Migration Requirement"
        verbose_name_plural = "Prodoc Migration Requirements"
        unique_together = [("workspace", "slug")]
        indexes = [models.Index(fields=["workspace", "slug"])]

    def __str__(self):
        return f"{self.slug} ({self.workspace.slug})"


class ProdocThirdPartyTool(BaseModel):
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="prodoc_third_party_tools",
    )
    slug = models.SlugField(
        max_length=120,
        help_text=(
            "Stable workspace-scoped handle referenced from template task "
            "`third_party_tool_slugs` JSON lists."
        ),
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=40, choices=TOOL_CATEGORY_CHOICES, default="other"
    )
    default_owner_role = models.CharField(max_length=50)

    class Meta:
        db_table = "prodoc_third_party_tools"
        verbose_name = "Prodoc Third-Party Tool"
        verbose_name_plural = "Prodoc Third-Party Tools"
        unique_together = [("workspace", "slug")]
        indexes = [models.Index(fields=["workspace", "slug"])]

    def __str__(self):
        return f"{self.slug} ({self.workspace.slug})"
