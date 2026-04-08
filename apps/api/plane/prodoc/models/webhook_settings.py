"""
Sidecar settings model for upstream `Webhook`.

We are not allowed to add fields to the upstream `Webhook` model
(`apps/api/plane/db/models/webhook.py`) per CLAUDE.md §2 — Django won't
expose a column to the ORM unless the field is declared on the model
class, and editing that file is forbidden.

`ProdocWebhookSettings` is a OneToOne sidecar that holds Prodoc-specific
opt-in flags. Today it carries one field (`dependency`); future
extensions can add more without re-touching the upstream model.

The relationship is intentionally lazy: rows are NOT backfilled when a
new `Webhook` is created. The dispatcher in `plane.prodoc.tasks` reads
via `Webhook.objects.filter(prodoc_settings__dependency=True)`, which
inner-joins against the sidecar table and naturally excludes webhooks
that have not opted in. Webhooks with no sidecar row behave exactly as
if `dependency=False`, which is the correct default.
"""

from django.db import models

from plane.db.models import BaseModel, Webhook


class ProdocWebhookSettings(BaseModel):
    webhook = models.OneToOneField(
        Webhook,
        on_delete=models.CASCADE,
        related_name="prodoc_settings",
    )
    dependency = models.BooleanField(
        default=False,
        help_text=(
            "Opt in to prodoc.dependency.* webhook events (created, "
            "deleted, cascaded). Until set to True, the dispatcher in "
            "plane.prodoc.tasks falls back to the legacy Webhook.issue "
            "boolean for one release cycle (Extension 2 → Extension 3)."
        ),
    )

    class Meta:
        db_table = "prodoc_webhook_settings"
        verbose_name = "Prodoc Webhook Settings"
        verbose_name_plural = "Prodoc Webhook Settings"
