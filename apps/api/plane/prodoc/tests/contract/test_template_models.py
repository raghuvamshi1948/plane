# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Model-layer tests for ProdocTemplate and ProdocTemplateSection.

Verifies workspace tenant isolation, the (workspace, slug, version)
uniqueness contract, is_locked default, soft-delete filtering, and the
(template, order) section uniqueness.
"""

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from plane.prodoc.models import ProdocTemplate, ProdocTemplateSection


@pytest.mark.contract
class TestProdocTemplateModel:
    @pytest.mark.django_db
    def test_workspace_isolation_template_not_visible_in_other_workspace(
        self, workspace, second_workspace
    ):
        ProdocTemplate.objects.create(
            workspace=workspace,
            slug="onboarding",
            version="1.0",
            name="Healthcare Provider Onboarding",
        )
        # Query scoped to the other workspace must not see it.
        other_qs = ProdocTemplate.objects.filter(
            workspace=second_workspace["workspace"]
        )
        assert other_qs.count() == 0

    @pytest.mark.django_db
    def test_workspace_slug_version_uniqueness_enforced(self, workspace):
        ProdocTemplate.objects.create(
            workspace=workspace, slug="onboarding", version="1.0", name="A"
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProdocTemplate.objects.create(
                    workspace=workspace,
                    slug="onboarding",
                    version="1.0",
                    name="Dup",
                )

    @pytest.mark.django_db
    def test_same_slug_different_version_allowed(self, workspace):
        t1 = ProdocTemplate.objects.create(
            workspace=workspace, slug="onboarding", version="1.0", name="v1"
        )
        t2 = ProdocTemplate.objects.create(
            workspace=workspace, slug="onboarding", version="1.1", name="v1.1"
        )
        assert t1.pk != t2.pk

    @pytest.mark.django_db
    def test_is_locked_defaults_to_false_and_can_be_flipped(self, workspace):
        template = ProdocTemplate.objects.create(
            workspace=workspace, slug="t", version="1.0", name="T"
        )
        assert template.is_locked is False
        template.is_locked = True
        template.save()
        template.refresh_from_db()
        assert template.is_locked is True

    @pytest.mark.django_db
    def test_soft_delete_hides_row_from_tenant_query(self, workspace):
        template = ProdocTemplate.objects.create(
            workspace=workspace, slug="t", version="1.0", name="T"
        )
        template.deleted_at = timezone.now()
        template.save()

        visible = ProdocTemplate.objects.filter(
            workspace=workspace, deleted_at__isnull=True
        )
        assert visible.count() == 0

    @pytest.mark.django_db
    def test_section_order_uniqueness_per_template(self, workspace):
        template = ProdocTemplate.objects.create(
            workspace=workspace, slug="t", version="1.0", name="T"
        )
        ProdocTemplateSection.objects.create(
            template=template, name="Governance", order=1
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProdocTemplateSection.objects.create(
                    template=template, name="Access", order=1
                )

    @pytest.mark.django_db
    def test_section_same_order_different_template_allowed(self, workspace):
        t1 = ProdocTemplate.objects.create(
            workspace=workspace, slug="a", version="1.0", name="A"
        )
        t2 = ProdocTemplate.objects.create(
            workspace=workspace, slug="b", version="1.0", name="B"
        )
        s1 = ProdocTemplateSection.objects.create(template=t1, name="X", order=1)
        s2 = ProdocTemplateSection.objects.create(template=t2, name="Y", order=1)
        assert s1.pk != s2.pk
