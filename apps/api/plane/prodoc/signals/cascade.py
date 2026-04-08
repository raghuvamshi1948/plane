"""
Dependency cascade signal handler.

When a blocker work item's `target_date` slips forward, every downstream
work item connected via a `blocked_by` IssueRelation should slide
forward by the same number of *working days* (not calendar days) using
the resolved holiday calendar.

Why a signal and not a Celery task triggered explicitly:

- Catches every write path. Upstream's web frontend, API, future
  Extension 3 materializer ORM writes — anywhere `Issue.save()` runs,
  the cascade happens.
- No upstream `Issue.save()` modification needed (CLAUDE.md §2).

Why post_save and not post_delete:
    See `plane.prodoc.signals.dependency` and the build plan §5.10 (a).

Why pre_save snapshots the previous target_date:
    Django's post_save does not include the previous value. The
    canonical pattern is a pre_save receiver that loads the on-disk row
    and stashes the prior value into a thread-local keyed by pk; the
    post_save then reads and clears it.

Re-entry guard + explicit walker with visited set:
    The cascade itself is an explicit walker (`_cascade_walk`) that
    tracks a visited set of issue pks, so cycles like A→B→A terminate
    after each node is visited at most once.

    The walker calls `Issue.save()` on each updated downstream, which
    naturally re-fires this same post_save signal. We use a
    `threading.local()` "active" flag to short-circuit those signal-
    triggered recursive entries — we already handled the chain via the
    explicit walker, and re-walking from each downstream would
    re-traverse the graph quadratically.

    Net result: total Issue.save() calls during a cascade are bounded
    by 1 (the user's original save) + |reachable downstream nodes|.
    For a cycle of length N, that's at most 1 + N saves.

Idempotency:
    If a downstream item's recomputed target equals its current target,
    we skip the save entirely. This handles two cases:
    (a) the diamond scenario A→{B,C}→D where D is reached twice but the
        second arrival yields no movement;
    (b) any cascade re-application that would be a no-op.
"""

import threading

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from plane.db.models import Issue, IssueRelation
from plane.prodoc.scheduling.business_days import (
    add_business_days,
    count_business_days,
)
from plane.prodoc.scheduling.calendar_resolver import (
    parse_holidays,
    resolve_calendar_for_project,
)
from plane.prodoc.signals.dependency import _flag_enabled
from plane.prodoc.tasks import prodoc_dispatch_dependency_webhook


# Thread-local re-entry guard. While `active` is truthy, the cascade
# handler short-circuits — we are already inside a cascade-driven save
# chain in this thread.
_cascade_local = threading.local()

# Per-pk snapshot of the prior target_date, populated by pre_save and
# consumed by post_save.
_target_date_snapshot = threading.local()


def _get_snapshots():
    snapshots = getattr(_target_date_snapshot, "by_pk", None)
    if snapshots is None:
        snapshots = {}
        _target_date_snapshot.by_pk = snapshots
    return snapshots


@receiver(pre_save, sender=Issue, dispatch_uid="prodoc_cascade_pre_save")
def snapshot_target_date(sender, instance, **kwargs):
    """Capture the on-disk target_date before save() runs."""
    if instance.pk is None:
        return
    try:
        prior = Issue.objects.values_list("target_date", flat=True).get(pk=instance.pk)
    except Issue.DoesNotExist:
        return
    _get_snapshots()[instance.pk] = prior


@receiver(post_save, sender=Issue, dispatch_uid="prodoc_cascade_post_save")
def cascade_on_target_date_change(sender, instance, created, **kwargs):
    """Walk the blocked_by graph forward when target_date slips."""
    snapshots = _get_snapshots()
    prior = snapshots.pop(instance.pk, None)

    if created:
        return
    if instance.deleted_at is not None:
        return
    if not _flag_enabled():
        return
    # Re-entry guard: we are already inside a cascade walker on this thread.
    # The walker will handle deeper levels explicitly.
    if getattr(_cascade_local, "active", False):
        return
    # Nothing to cascade if the new target is null or unchanged.
    if instance.target_date is None:
        return
    if prior is None or prior == instance.target_date:
        return
    # Slack absorbs backward moves (build plan §6.2). Only forward slips
    # cascade.
    if instance.target_date <= prior:
        return

    # Resolve the blocker's own calendar so the working-day count is
    # measured against the same holiday list the cascade applies later.
    blocker_calendar = resolve_calendar_for_project(
        project_id=instance.project_id,
        workspace_id=instance.workspace_id,
    )
    blocker_holidays = (
        parse_holidays(blocker_calendar.holidays) if blocker_calendar else set()
    )
    delta_working_days = count_business_days(
        prior, instance.target_date, blocker_holidays
    )
    if delta_working_days <= 0:
        return

    _cascade_local.active = True
    try:
        # Single mutable visited set shared across the whole DFS.
        # The blocker is pre-seeded so we never re-cascade the origin.
        # Crucially, we also skip any downstream we've already touched
        # in this cascade run — the diamond scenario A→{B,C}→D needs
        # this so D is not double-shifted via two paths.
        _cascade_walk(
            blocker_id=instance.id,
            workspace_id=instance.workspace_id,
            delta_working_days=delta_working_days,
            visited={instance.id},
        )
    finally:
        _cascade_local.active = False


def _cascade_walk(blocker_id, workspace_id, delta_working_days, visited):
    """Recompute target_date on every issue blocked by `blocker_id`.

    Walker is depth-first with an explicit visited set so cycles
    terminate. Each downstream that actually moves recurses; downstreams
    that no-op (idempotency) or are already visited do not.

    Performance note: this iterates downstream issues one at a time and
    issues a save() per row. If profiling on Extension 3's materialized
    chains shows N+1 hot spots, the optimization path is:

        downstream_qs = (queryset above).select_related('project')
        Issue.objects.bulk_update(updated_issues, ['target_date'])
        # then manually re-trigger _cascade_walk on each updated issue

    Don't implement now — leave the breadcrumb. The current implementation
    is correct and supports the cycle/idempotency tests; bulk_update
    would skip pre_save/post_save and we'd lose the natural test
    coverage of the signal pipeline.
    """
    # Workspace-scoped per CLAUDE.md §3.
    relations = IssueRelation.objects.filter(
        related_issue_id=blocker_id,
        relation_type="blocked_by",
        workspace_id=workspace_id,
        deleted_at__isnull=True,
    ).select_related("issue")

    for rel in relations:
        downstream = rel.issue
        if downstream.id in visited:
            # Already touched in this cascade run (diamond join, or
            # cycle). Skip — we apply the slip exactly once per node.
            continue
        # Skip downstream items that have no target_date set — there is
        # nothing to slip. Don't error, don't fire a webhook.
        if downstream.target_date is None:
            visited.add(downstream.id)
            continue

        calendar = resolve_calendar_for_project(
            project_id=downstream.project_id,
            workspace_id=downstream.workspace_id,
        )
        holidays = parse_holidays(calendar.holidays) if calendar else set()

        new_target = add_business_days(
            downstream.target_date, delta_working_days, holidays
        )

        # Mark visited BEFORE the save so any signal-triggered re-entry
        # (or recursive walker call below) sees this node as done.
        visited.add(downstream.id)

        # Idempotency: if the recomputed target equals the current value
        # (no movement to apply), skip the save and the webhook but
        # still descend in case downstream items would move.
        if new_target != downstream.target_date:
            downstream.target_date = new_target
            downstream.save(update_fields=["target_date", "updated_at"])

            prodoc_dispatch_dependency_webhook.delay(
                action="cascaded",
                relation_id=str(rel.id),
                workspace_id=str(downstream.workspace_id),
                project_id=str(downstream.project_id),
                issue_id=str(downstream.id),
                related_issue_id=str(blocker_id),
                relation_type="blocked_by",
            )

        # Recurse into this downstream's own blocked_by edges, sharing
        # the same visited set.
        _cascade_walk(
            blocker_id=downstream.id,
            workspace_id=downstream.workspace_id,
            delta_working_days=delta_working_days,
            visited=visited,
        )
