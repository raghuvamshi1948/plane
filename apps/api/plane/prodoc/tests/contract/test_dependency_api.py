# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# NOTE: These are the first IssueRelation tests in this fork. Upstream Plane
# ships GET/POST for relations at apps/api/plane/api/views/issue.py:2266 but
# has no test coverage for the endpoint and no DELETE method. This file
# tests the prodoc-side DELETE endpoint and its associated webhook signal.

from unittest.mock import patch
from uuid import uuid4

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import IssueRelation, Project, ProjectMember


def _url(workspace_slug, project_id, issue_id, relation_id):
    return (
        f"/api/v1/prodoc/workspaces/{workspace_slug}"
        f"/projects/{project_id}/work-items/{issue_id}/relations/{relation_id}/"
    )


def _flag_on():
    """Patch helper: ProdocFeatureFlagMixin and signal helper both call
    get_configuration_value. Patch both call sites to return ('1',)."""
    return patch(
        "plane.prodoc.views.base.get_configuration_value",
        return_value=("1",),
    )


def _signal_flag_on():
    return patch(
        "plane.prodoc.signals.dependency.get_configuration_value",
        return_value=("1",),
    )


@pytest.mark.contract
class TestProdocDependencyDeleteEndpoint:
    """DELETE /api/v1/prodoc/.../relations/<relation_id>/"""

    @pytest.mark.django_db
    def test_delete_relation_happy_path(
        self, api_key_client, workspace, project, issue_factory, relation_factory
    ):
        a = issue_factory(project)
        b = issue_factory(project)
        relation = relation_factory(a, b, "blocked_by")

        with _flag_on():
            response = api_key_client.delete(
                _url(workspace.slug, project.id, a.id, relation.id)
            )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not IssueRelation.objects.filter(pk=relation.id).exists()

    @pytest.mark.django_db
    def test_delete_returns_404_for_nonexistent_relation(
        self, api_key_client, workspace, project, issue_factory
    ):
        a = issue_factory(project)
        with _flag_on():
            response = api_key_client.delete(
                _url(workspace.slug, project.id, a.id, uuid4())
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.django_db
    def test_delete_returns_404_when_relation_belongs_to_different_project(
        self, api_key_client, workspace, project, create_user, issue_factory, relation_factory
    ):
        # Create a second project in the same workspace; create the relation
        # there. Then attempt to delete it via the first project's URL.
        other_project = Project.objects.create(
            name="Second Project",
            identifier="SP",
            workspace=workspace,
            created_by=create_user,
        )
        ProjectMember.objects.create(
            project=other_project,
            workspace=workspace,
            member=create_user,
            role=20,
            is_active=True,
        )
        a = issue_factory(other_project)
        b = issue_factory(other_project)
        relation = relation_factory(a, b, "blocked_by")

        with _flag_on():
            response = api_key_client.delete(
                _url(workspace.slug, project.id, a.id, relation.id)
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert IssueRelation.objects.filter(pk=relation.id).exists()

    @pytest.mark.django_db
    def test_delete_returns_404_when_issue_id_not_party_to_relation(
        self, api_key_client, workspace, project, issue_factory, relation_factory
    ):
        a = issue_factory(project)
        b = issue_factory(project)
        c = issue_factory(project)  # not party to the relation
        relation = relation_factory(a, b, "blocked_by")

        with _flag_on():
            response = api_key_client.delete(
                _url(workspace.slug, project.id, c.id, relation.id)
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert IssueRelation.objects.filter(pk=relation.id).exists()

    @pytest.mark.django_db
    def test_workspace_isolation_cross_tenant_returns_404(
        self,
        api_client,
        workspace,
        project,
        issue_factory,
        relation_factory,
        second_workspace,
    ):
        # Create a relation in workspace A.
        a = issue_factory(project)
        b = issue_factory(project)
        relation = relation_factory(a, b, "blocked_by")

        # Authenticate with workspace B's API key.
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=second_workspace["token"].token)

        with _flag_on():
            # Use workspace A's URL but B's credentials.
            response = client.delete(
                _url(workspace.slug, project.id, a.id, relation.id)
            )

        # Permission class denies — DRF returns 403 from a permission failure
        # by default; cross-workspace lookups for nonexistent membership
        # commonly surface as either 403 or 404. Either way, the row must
        # NOT be deleted. Assert both: the row survives, and the response
        # is in the deny set (not 204).
        assert response.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )
        assert IssueRelation.objects.filter(pk=relation.id).exists()

    @pytest.mark.django_db
    def test_workspace_member_not_in_project_cannot_delete(
        self, api_key_client, workspace, project, create_user, issue_factory, relation_factory
    ):
        # Remove the user from the project, leaving them as a workspace
        # member only. ProjectEntityPermission should reject the DELETE.
        ProjectMember.objects.filter(project=project, member=create_user).delete()

        a = issue_factory(project)
        b = issue_factory(project)
        relation = relation_factory(a, b, "blocked_by")

        with _flag_on():
            response = api_key_client.delete(
                _url(workspace.slug, project.id, a.id, relation.id)
            )

        # ProjectEntityPermission denies — DRF returns 403 by default.
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert IssueRelation.objects.filter(pk=relation.id).exists()

    @pytest.mark.django_db
    def test_feature_flag_disabled_returns_404(
        self, api_key_client, workspace, project, issue_factory, relation_factory
    ):
        a = issue_factory(project)
        b = issue_factory(project)
        relation = relation_factory(a, b, "blocked_by")

        # Default test env has the flag off; explicitly patch to confirm.
        with patch(
            "plane.prodoc.views.base.get_configuration_value",
            return_value=("0",),
        ):
            response = api_key_client.delete(
                _url(workspace.slug, project.id, a.id, relation.id)
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert IssueRelation.objects.filter(pk=relation.id).exists()

    @pytest.mark.django_db
    def test_signal_fires_created_on_orm_create(
        self, workspace, project, issue_factory, webhook_factory
    ):
        # Webhook so the dispatcher would actually have something to fan
        # out to in production. Test asserts the dispatcher .delay() was
        # called with the right kwargs.
        webhook_factory(workspace)
        a = issue_factory(project)
        b = issue_factory(project)

        with _signal_flag_on(), patch(
            "plane.prodoc.signals.dependency.prodoc_dispatch_dependency_webhook"
        ) as mock_task:
            IssueRelation.objects.create(
                issue=a,
                related_issue=b,
                relation_type="blocked_by",
                project=project,
                workspace=workspace,
            )

        assert mock_task.delay.called
        kwargs = mock_task.delay.call_args.kwargs
        assert kwargs["action"] == "created"
        assert kwargs["issue_id"] == str(a.id)
        assert kwargs["related_issue_id"] == str(b.id)
        assert kwargs["relation_type"] == "blocked_by"
        assert kwargs["workspace_id"] == str(workspace.id)
        assert kwargs["project_id"] == str(project.id)

    @pytest.mark.django_db
    def test_signal_fires_deleted_on_prodoc_delete_endpoint(
        self,
        api_key_client,
        workspace,
        project,
        issue_factory,
        relation_factory,
        webhook_factory,
    ):
        webhook_factory(workspace)
        a = issue_factory(project)
        b = issue_factory(project)
        relation = relation_factory(a, b, "blocked_by")

        with _flag_on(), _signal_flag_on(), patch(
            "plane.prodoc.signals.dependency.prodoc_dispatch_dependency_webhook"
        ) as mock_task:
            response = api_key_client.delete(
                _url(workspace.slug, project.id, a.id, relation.id)
            )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert mock_task.delay.called
        # Filter to the deleted call (post_save with created=True does not
        # fire on factory create above; only post_delete should hit here).
        delete_calls = [c for c in mock_task.delay.call_args_list if c.kwargs.get("action") == "deleted"]
        assert len(delete_calls) >= 1
        kwargs = delete_calls[0].kwargs
        assert kwargs["relation_id"] == str(relation.id)
        assert kwargs["relation_type"] == "blocked_by"

    @pytest.mark.django_db
    def test_signal_no_op_when_flag_disabled(
        self, workspace, project, issue_factory
    ):
        a = issue_factory(project)
        b = issue_factory(project)

        with patch(
            "plane.prodoc.signals.dependency.get_configuration_value",
            return_value=("0",),
        ), patch(
            "plane.prodoc.signals.dependency.prodoc_dispatch_dependency_webhook"
        ) as mock_task:
            IssueRelation.objects.create(
                issue=a,
                related_issue=b,
                relation_type="blocked_by",
                project=project,
                workspace=workspace,
            )

        assert not mock_task.delay.called
