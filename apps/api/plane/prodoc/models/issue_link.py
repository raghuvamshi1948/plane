"""
Sidecar model linking a Plane `Issue` to its Prodoc metadata.

`ProdocIssueLink` is the C2 resolution for custom properties (see the
Ext 3 plan file): rather than extend Plane's `IssueType` / `IssueProperty`
(which CE doesn't have typed-property infrastructure for anyway), every
materialized work item gets a one-to-one sidecar carrying the bits that
only Prodoc cares about — which template task produced it, which site
and/or wave it belongs to, the SLA bucket, and the typed many-to-many
references into the workspace's migration-requirement and third-party-
tool catalogs.

Why OneToOne and not FK: a Plane issue represents at most one template
task in a materialized tree. Re-materializing the same template into
the same project bumps the template version and creates *new* issues,
not new links on old issues.

Why `workspace` and `project` are denormalized: the tenant-filter path
is `ProdocIssueLink.objects.filter(workspace=...)`, and joining through
`Issue` to recover the workspace would break the workspace-first
queryset pattern CLAUDE.md §3 requires. Denormalization here costs a
column and pays for itself on every list endpoint.

The materializer (`plane.prodoc.materialization.engine.materialize`) is
the sole write path in Ext 3. The REST API exposes the link read-only
so consumers can render SLA + requirement tags on the Plane UI without
editing the upstream issue model.
"""

from django.db import models

from plane.db.models import BaseModel, Project, Workspace

from .reference import ProdocMigrationRequirement, ProdocThirdPartyTool
from .site import ProdocSite
from .template_task import ProdocTemplateTask
from .wave import ProdocWave


class ProdocIssueLink(BaseModel):
    issue = models.OneToOneField(
        "db.Issue",
        on_delete=models.CASCADE,
        related_name="prodoc_link",
    )
    # Denormalized for tenant-filter queries (CLAUDE.md §3 — the first
    # line of every get_queryset is the workspace filter; having this
    # column avoids a join through `issue` for every list page).
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="prodoc_issue_links",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="prodoc_issue_links",
    )
    template_task = models.ForeignKey(
        ProdocTemplateTask,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issue_links",
    )
    site = models.ForeignKey(
        ProdocSite,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issue_links",
    )
    wave = models.ForeignKey(
        ProdocWave,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issue_links",
    )
    sla_hours = models.IntegerField(null=True, blank=True)
    migration_requirements = models.ManyToManyField(
        ProdocMigrationRequirement,
        blank=True,
        related_name="linked_issues",
    )
    third_party_tools = models.ManyToManyField(
        ProdocThirdPartyTool,
        blank=True,
        related_name="linked_issues",
    )

    class Meta:
        db_table = "prodoc_issue_links"
        verbose_name = "Prodoc Issue Link"
        verbose_name_plural = "Prodoc Issue Links"
        indexes = [
            models.Index(fields=["workspace", "template_task"]),
            models.Index(fields=["workspace", "site"]),
            models.Index(fields=["workspace", "wave"]),
        ]

    def __str__(self):
        return f"prodoc-link<{self.issue_id}>"
