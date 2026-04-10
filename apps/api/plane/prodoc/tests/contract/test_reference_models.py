# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Model-layer tests for ProdocMigrationRequirement and ProdocThirdPartyTool.

Verifies (workspace, slug) uniqueness, workspace isolation, and that
the slug column is present and usable — the materializer (commit 5)
will rely on this field to resolve template JSONField slug lists.
"""

import pytest
from django.db import IntegrityError, transaction

from plane.prodoc.models import ProdocMigrationRequirement, ProdocThirdPartyTool


@pytest.mark.contract
class TestReferenceModels:
    @pytest.mark.django_db
    def test_migration_requirement_workspace_slug_unique(self, workspace):
        ProdocMigrationRequirement.objects.create(
            workspace=workspace,
            slug="req-data-export",
            name="Data export",
            category="data",
            default_owner_role="admin",
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProdocMigrationRequirement.objects.create(
                    workspace=workspace,
                    slug="req-data-export",
                    name="Dup",
                    category="data",
                    default_owner_role="admin",
                )

    @pytest.mark.django_db
    def test_migration_requirement_same_slug_different_workspace_allowed(
        self, workspace, second_workspace
    ):
        ProdocMigrationRequirement.objects.create(
            workspace=workspace,
            slug="req-data-export",
            name="A",
            category="data",
            default_owner_role="admin",
        )
        ProdocMigrationRequirement.objects.create(
            workspace=second_workspace["workspace"],
            slug="req-data-export",
            name="B",
            category="data",
            default_owner_role="admin",
        )
        assert ProdocMigrationRequirement.objects.count() == 2

    @pytest.mark.django_db
    def test_third_party_tool_workspace_slug_unique(self, workspace):
        ProdocThirdPartyTool.objects.create(
            workspace=workspace,
            slug="tool-salesforce",
            name="Salesforce",
            category="crm",
            default_owner_role="admin",
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProdocThirdPartyTool.objects.create(
                    workspace=workspace,
                    slug="tool-salesforce",
                    name="Dup",
                    category="crm",
                    default_owner_role="admin",
                )

    @pytest.mark.django_db
    def test_workspace_isolation_hidden_from_other_workspace_query(
        self, workspace, second_workspace
    ):
        ProdocMigrationRequirement.objects.create(
            workspace=workspace,
            slug="req-x",
            name="X",
            category="other",
            default_owner_role="admin",
        )
        qs = ProdocMigrationRequirement.objects.filter(
            workspace=second_workspace["workspace"]
        )
        assert qs.count() == 0
