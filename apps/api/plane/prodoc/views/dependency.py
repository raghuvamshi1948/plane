import json

from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView
from plane.bgtasks.issue_activities_task import issue_activity
from plane.db.models import IssueRelation
from plane.prodoc.permissions.project import ProdocProjectEntityPermission
from plane.prodoc.views.base import ProdocFeatureFlagMixin
from plane.utils.host import base_host


class IssueRelationDeleteAPIEndpoint(ProdocFeatureFlagMixin, BaseAPIView):
    """
    Delete a single IssueRelation by id.

    Mirrors the semantics of the internal app viewset's `remove_relation`
    (apps/api/plane/app/views/issue/relation.py:262), but accepts the
    relation id directly in the URL rather than the (issue, related_issue)
    pair in the request body, so it composes cleanly with REST conventions.

    Upstream's public IssueRelationListCreateAPIEndpoint
    (apps/api/plane/api/views/issue.py:2266) provides GET and POST but no
    DELETE; this endpoint fills that gap.
    """

    permission_classes = [ProdocProjectEntityPermission]
    use_read_replica = False

    def delete(self, request, slug, project_id, issue_id, relation_id):
        # Workspace + project scope is enforced by the permission class.
        # We additionally constrain the lookup to defend in depth.
        try:
            relation = IssueRelation.objects.get(
                pk=relation_id,
                workspace__slug=slug,
                project_id=project_id,
            )
        except IssueRelation.DoesNotExist:
            return Response(
                {"error": "Issue relation not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Defend against URL tampering: the relation_id must actually
        # involve the issue_id from the URL on one side or the other.
        if str(relation.issue_id) != str(issue_id) and str(relation.related_issue_id) != str(issue_id):
            return Response(
                {"error": "Issue relation not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Snapshot for activity log (matches upstream `remove_relation`).
        # Local import to avoid pulling plane.app.serializers at module load.
        from plane.app.serializers import IssueRelationSerializer

        current_instance = json.dumps(
            IssueRelationSerializer(relation).data,
            cls=DjangoJSONEncoder,
        )

        related_issue_for_payload = (
            relation.related_issue_id
            if str(relation.issue_id) == str(issue_id)
            else relation.issue_id
        )

        # Soft-delete per CLAUDE.md §5. IssueRelation inherits from
        # SoftDeleteModel via ProjectBaseModel, so calling .delete()
        # would set deleted_at and save(). We do that explicitly so the
        # behavior is obvious and the post_save signal handler in
        # plane.prodoc.signals.dependency reliably observes the
        # deleted_at transition.
        relation.deleted_at = timezone.now()
        relation.save()

        # Activity log entry (matches upstream's payload shape so the
        # Plane in-app activity renderer treats it identically).
        issue_activity.delay(
            type="issue_relation.activity.deleted",
            requested_data=json.dumps(
                {"related_issue": str(related_issue_for_payload)},
                cls=DjangoJSONEncoder,
            ),
            actor_id=str(request.user.id),
            issue_id=str(issue_id),
            project_id=str(project_id),
            current_instance=current_instance,
            epoch=int(timezone.now().timestamp()),
            notification=True,
            origin=base_host(request=request, is_app=True),
        )

        return Response(status=status.HTTP_204_NO_CONTENT)
