import traceback

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from plane.bgtasks.webhook_task import webhook_send_task
from plane.db.models import Issue, IssueRelation, Module, Webhook


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


@shared_task(name="prodoc_materialize_project", max_retries=0)
def prodoc_materialize_project(job_id):
    """Execute a queued ProdocMaterializationJob against the database.

    Lifecycle:
        queued → running → (succeeded | failed)

    Transaction boundary:
        The wet-run engine writes ~180 rows per call (~120 Issues,
        ~60 relations, plus sidecars and modules). Every write is
        wrapped in a single `transaction.atomic()` so a mid-run
        failure leaves zero rows committed. The job bookkeeping write
        (`status='failed'`, `error_log=traceback`, `finished_at=now`)
        happens in a **separate** atomic block outside the rolled-back
        one, so the failure record survives even though the work itself
        did not.

    Cascade suppression:
        Wraps the engine in `cascade_suppressed()` so Ext 2's
        post_save cascade walker doesn't re-traverse the dependency
        graph on every Issue.save() during construction. The context
        manager is scoped to the engine block — subsequent saves in
        any other request still fire the cascade normally.

    Retries (C3 resolution — see Ext 3 plan file):
        `max_retries=0`. Matches build plan §7.7 step 11 verbatim.
        A failed job is terminal; ops re-runs explicitly. The engine's
        atomic transaction is the safety boundary — there is nothing
        half-written to clean up, so there's no "am I a retry" state
        to detect and no rollback pass to re-run.

    Template locking:
        On success, we flip `template.is_locked=True` so further edits
        require a version bump. Commit 8's REST API enforces this on
        PATCH with a 409. The flip lives inside the success branch
        because a failed materialization should not lock the template.
    """
    # Lazy imports: the task module is loaded by Celery workers at boot
    # before the Django app registry is fully primed. Models are safe at
    # call time but not at import time.
    from plane.prodoc.materialization import build_plan
    from plane.prodoc.materialization.engine import materialize
    from plane.prodoc.models import (
        ProdocMaterializationJob,
        ProdocSite,
        ProdocWave,
    )
    from plane.prodoc.signals.cascade import cascade_suppressed

    job = ProdocMaterializationJob.objects.select_related(
        "template", "project", "workspace"
    ).get(id=job_id)

    # Status transition: queued → running. A small atomic block so the
    # running status is visible to any poller that hits the GET endpoint
    # between here and the first engine write.
    with transaction.atomic():
        job.status = "running"
        job.started_at = timezone.now()
        job.save(update_fields=["status", "started_at", "updated_at"])

    project = job.project
    template = job.template
    sites = list(
        ProdocSite.objects.filter(
            project=project, deleted_at__isnull=True
        )
    )
    waves = list(
        ProdocWave.objects.filter(
            project=project, deleted_at__isnull=True
        ).order_by("order")
    )

    try:
        with transaction.atomic():
            with cascade_suppressed():
                plan = build_plan(
                    template=template,
                    project=project,
                    start_date=job.start_date,
                    sites=sites,
                    waves=waves,
                )
                materialize(plan, project, job=job, dry_run=False)

                # Success branch is *inside* the atomic block so the
                # status flip + the work items commit together. If the
                # flip itself failed (it shouldn't, but), the whole
                # transaction unwinds and we fall through to the except.
                job.status = "succeeded"
                job.finished_at = timezone.now()
                job.save(
                    update_fields=[
                        "status",
                        "finished_at",
                        "work_items_created",
                        "modules_created",
                        "relations_created",
                        "error_log",
                        "updated_at",
                    ]
                )
                # Lock the template — further edits require a bump.
                template.is_locked = True
                template.save(update_fields=["is_locked", "updated_at"])
    except Exception:
        # Separate transaction so the failure record survives the
        # rolled-back work. We don't need to soft-delete created rows
        # because the atomic block above rolled them back wholesale;
        # the job's _created lists reflect what we *attempted*, useful
        # for the post-mortem even though nothing landed on disk.
        error_text = traceback.format_exc()
        with transaction.atomic():
            job.refresh_from_db()
            job.status = "failed"
            job.error_log = error_text
            job.finished_at = timezone.now()
            job.save(
                update_fields=[
                    "status",
                    "error_log",
                    "finished_at",
                    "updated_at",
                ]
            )
        raise
