import os

from django.db.models.signals import post_save
from django.dispatch import receiver

from plane.db.models import IssueRelation
from plane.license.utils.instance_value import get_configuration_value
from plane.prodoc.tasks import prodoc_dispatch_dependency_webhook


def _flag_enabled():
    (PRODOC_FEATURES_ENABLED,) = get_configuration_value(
        [
            {
                "key": "PRODOC_FEATURES_ENABLED",
                "default": os.environ.get("PRODOC_FEATURES_ENABLED", "0"),
            }
        ]
    )
    return PRODOC_FEATURES_ENABLED == "1"


@receiver(post_save, sender=IssueRelation, dispatch_uid="prodoc_relation_post_save")
def on_relation_save(sender, instance, created, **kwargs):
    """
    Single post_save handler that detects both creates and soft-deletes.

    Plane's SoftDeleteModel.delete() (apps/api/plane/db/mixins.py:72) sets
    `deleted_at` and calls save() rather than performing a hard DELETE,
    which means post_delete never fires for relation removal — only
    post_save does, with `created=False` and `deleted_at` populated.
    Detecting the transition here is the only reliable way to fan out
    both `prodoc.dependency.created` and `prodoc.dependency.deleted`
    events for every write path (upstream POST, prodoc DELETE, future
    Extension 3 ORM writes).

    IssueRelation is otherwise effectively immutable, so any post_save
    that is neither a fresh create nor a soft-delete (e.g., a no-op
    re-save) is ignored.
    """
    if created:
        action = "created"
    elif instance.deleted_at is not None:
        action = "deleted"
    else:
        return

    if not _flag_enabled():
        return

    prodoc_dispatch_dependency_webhook.delay(
        action=action,
        relation_id=str(instance.id),
        workspace_id=str(instance.workspace_id),
        project_id=str(instance.project_id),
        issue_id=str(instance.issue_id),
        related_issue_id=str(instance.related_issue_id),
        relation_type=instance.relation_type,
    )
