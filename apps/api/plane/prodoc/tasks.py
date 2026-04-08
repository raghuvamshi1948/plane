from celery import shared_task
from django.conf import settings

from plane.bgtasks.webhook_task import webhook_send_task
from plane.db.models import Webhook


@shared_task
def prodoc_dispatch_dependency_webhook(
    action,
    relation_id,
    workspace_id,
    project_id,
    issue_id,
    related_issue_id,
    relation_type,
):
    """
    Fan out a prodoc.dependency.<created|deleted> webhook event to all
    active webhooks in the workspace that have opted in.

    Opt-in resolution (added in Extension 2):

    1. **Primary** — `ProdocWebhookSettings.dependency=True`. The sidecar
       lives in `plane.prodoc.models.webhook_settings` and joins through
       the `Webhook.prodoc_settings` reverse relation. Webhooks without a
       sidecar row are excluded from this filter via inner-join semantics,
       which is the correct default ("not opted in").
    2. **Fallback** — `Webhook.issue=True` for any webhook NOT already in
       the primary set. This is the Extension 1 piggyback opt-in, kept
       for one release cycle so existing customer webhooks keep
       receiving prodoc.dependency.* events without explicit migration.

    TODO(ext3): drop the Webhook.issue fallback once all customer
    webhooks have explicitly opted in via ProdocWebhookSettings.dependency.
    """
    event_name = f"prodoc.dependency.{action}"

    # current_site matches base_host(is_app=True) semantics — that helper
    # reads these settings directly without touching the request, so we
    # can replicate its output from a Celery task.
    current_site = settings.WEB_URL or settings.APP_BASE_URL or ""

    primary_qs = Webhook.objects.filter(
        workspace_id=workspace_id,
        is_active=True,
        deleted_at__isnull=True,
        prodoc_settings__dependency=True,
    )
    fallback_qs = Webhook.objects.filter(
        workspace_id=workspace_id,
        is_active=True,
        deleted_at__isnull=True,
        issue=True,
    ).exclude(prodoc_settings__dependency=True)
    webhook_qs = (primary_qs | fallback_qs).distinct()

    workspace_slug = webhook_qs.values_list("workspace__slug", flat=True).first()
    if workspace_slug is None:
        return

    payload = {
        "id": relation_id,
        "issue": issue_id,
        "related_issue": related_issue_id,
        "relation_type": relation_type,
        "project": project_id,
        "workspace": workspace_id,
    }

    # Map our prodoc action verb to the HTTP-style action webhook_send_task
    # normalizes via its internal {POST: create, DELETE: delete, ...} table.
    # "cascaded" (Ext 2) is treated as an update.
    http_action = {
        "created": "POST",
        "deleted": "DELETE",
        "cascaded": "PATCH",
    }.get(action, "POST")

    for webhook in webhook_qs:
        webhook_send_task.delay(
            webhook_id=str(webhook.id),
            slug=workspace_slug,
            event=event_name,
            event_data=payload,
            action=http_action,
            current_site=current_site,
            activity={
                "field": None,
                "new_value": None,
                "old_value": None,
                "actor": None,
                "old_identifier": None,
                "new_identifier": None,
            },
        )
