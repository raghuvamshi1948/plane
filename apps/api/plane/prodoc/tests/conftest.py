# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Reuse the upstream test fixtures (api_client, api_key_client, workspace,
# create_user, api_token) from plane/tests/conftest.py. They live at a
# sibling path, not an ancestor, so pytest does not pick them up
# automatically — declare the module as a plugin instead.
pytest_plugins = ["plane.tests.conftest"]

import pytest

from plane.db.models import (
    Issue,
    IssueRelation,
    Project,
    ProjectMember,
    User,
    Webhook,
    Workspace,
    WorkspaceMember,
)
from plane.db.models.api import APIToken


@pytest.fixture
def project(db, workspace, create_user):
    """Create a test project with the user as a project admin."""
    project = Project.objects.create(
        name="Prodoc Test Project",
        identifier="PTP",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(
        project=project,
        workspace=workspace,
        member=create_user,
        role=20,  # Admin
        is_active=True,
    )
    return project


@pytest.fixture
def second_workspace(db):
    """A completely separate workspace+user+token for cross-tenant tests."""
    other_user = User.objects.create(
        email="other@plane.so",
        username="other_user",
        first_name="Other",
        last_name="User",
    )
    other_user.set_password("other-password")
    other_user.save()

    other_ws = Workspace.objects.create(
        name="Other Workspace",
        owner=other_user,
        slug="other-workspace",
    )
    WorkspaceMember.objects.create(workspace=other_ws, member=other_user, role=20)

    other_project = Project.objects.create(
        name="Other Project",
        identifier="OTH",
        workspace=other_ws,
        created_by=other_user,
    )
    ProjectMember.objects.create(
        project=other_project,
        workspace=other_ws,
        member=other_user,
        role=20,
        is_active=True,
    )

    other_token = APIToken.objects.create(
        user=other_user,
        label="Other API Token",
        token="other-api-token-67890",
    )

    return {
        "user": other_user,
        "workspace": other_ws,
        "project": other_project,
        "token": other_token,
    }


@pytest.fixture
def issue_factory(db, create_user):
    """Factory producing issues in the given project."""
    counter = {"n": 0}

    def _make(project, name=None):
        counter["n"] += 1
        return Issue.objects.create(
            name=name or f"Issue {counter['n']}",
            project=project,
            workspace=project.workspace,
            created_by=create_user,
        )

    return _make


@pytest.fixture
def relation_factory(db):
    """Factory producing IssueRelation rows directly via the ORM."""

    def _make(issue, related_issue, relation_type="blocked_by"):
        return IssueRelation.objects.create(
            issue=issue,
            related_issue=related_issue,
            relation_type=relation_type,
            project=issue.project,
            workspace=issue.workspace,
        )

    return _make


@pytest.fixture
def webhook_factory(db):
    """Factory producing active `issue=True` webhooks in a workspace."""
    counter = {"n": 0}

    def _make(workspace, url=None):
        counter["n"] += 1
        return Webhook.objects.create(
            workspace=workspace,
            url=url or f"https://example.com/webhook/{counter['n']}",
            is_active=True,
            issue=True,
        )

    return _make
