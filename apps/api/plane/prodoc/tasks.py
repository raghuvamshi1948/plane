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
    active webhooks in the workspace that are subscribed to issue events.

    Piggybacks on the existing Webhook.issue boolean opt-in. The Webhook
    model has no `issue_relation` / `dependency` field and we are not
    allowed to add one in Extension 1 (it's an upstream model).
    Subscribers to issue events implicitly receive dependency events;
    this is documented in the Extension 1 build notes as a known
    limitation, to be resolved in Extension 2 by adding a dedicated
    Webhook.dependency field.
    """
    event_name = f"prodoc.dependency.{action}"

    # current_site matches base_host(is_app=True) semantics — that helper
    # reads these settings directly without touching the request, so we
    # can replicate its output from a Celery task.
    current_site = settings.WEB_URL or settings.APP_BASE_URL or ""

    webhook_qs = Webhook.objects.filter(
        workspace_id=workspace_id,
        is_active=True,
        issue=True,
        deleted_at__isnull=True,
    )

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
    http_action = {"created": "POST", "deleted": "DELETE"}.get(action, "POST")

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
