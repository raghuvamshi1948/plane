# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Model-layer tests for ProdocSite, ProdocWave, and ProdocWaveSite.

Verifies project-scoping, wave ordering uniqueness, wave→site M2M via
the through table, and that `plane_module` FK defaults to null so the
materializer (not the model) is responsible for creating the mirror
Module.
"""

import pytest
from django.db import IntegrityError, transaction

from plane.db.models import Project, ProjectMember
from plane.prodoc.models import ProdocSite, ProdocWave, ProdocWaveSite


@pytest.fixture
def second_project(db, workspace, create_user):
    """Second project in the same workspace, for project-isolation tests."""
    proj = Project.objects.create(
        name="Second Prodoc Project",
        identifier="PTP2",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(
        project=proj,
        workspace=workspace,
        member=create_user,
        role=20,
        is_active=True,
    )
    return proj


@pytest.mark.contract
class TestProdocSiteModel:
    @pytest.mark.django_db
    def test_project_code_uniqueness_enforced(self, workspace, project):
        ProdocSite.objects.create(
            workspace=workspace, project=project, name="Hospital One", code="H1"
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProdocSite.objects.create(
                    workspace=workspace,
                    project=project,
                    name="Hospital Dup",
                    code="H1",
                )

    @pytest.mark.django_db
    def test_same_code_different_project_allowed(
        self, workspace, project, second_project
    ):
        ProdocSite.objects.create(
            workspace=workspace, project=project, name="H1", code="H1"
        )
        ProdocSite.objects.create(
            workspace=workspace, project=second_project, name="H1b", code="H1"
        )
        assert ProdocSite.objects.count() == 2

    @pytest.mark.django_db
    def test_project_isolation_via_queryset(
        self, workspace, project, second_project
    ):
        ProdocSite.objects.create(
            workspace=workspace, project=project, name="H1", code="H1"
        )
        qs = ProdocSite.objects.filter(project=second_project)
        assert qs.count() == 0


@pytest.mark.contract
class TestProdocWaveModel:
    @pytest.mark.django_db
    def test_wave_name_and_order_unique_per_project(self, workspace, project):
        ProdocWave.objects.create(
            workspace=workspace, project=project, name="Wave 1", order=1
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProdocWave.objects.create(
                    workspace=workspace,
                    project=project,
                    name="Wave 1",
                    order=2,
                )

    @pytest.mark.django_db
    def test_wave_order_unique_per_project(self, workspace, project):
        ProdocWave.objects.create(
            workspace=workspace, project=project, name="Wave 1", order=1
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProdocWave.objects.create(
                    workspace=workspace,
                    project=project,
                    name="Wave 2",
                    order=1,
                )

    @pytest.mark.django_db
    def test_plane_module_defaults_null(self, workspace, project):
        wave = ProdocWave.objects.create(
            workspace=workspace, project=project, name="Wave 1", order=1
        )
        assert wave.plane_module_id is None

    @pytest.mark.django_db
    def test_wave_site_through_enforces_unique_pair(
        self, workspace, project
    ):
        wave = ProdocWave.objects.create(
            workspace=workspace, project=project, name="W", order=1
        )
        site = ProdocSite.objects.create(
            workspace=workspace, project=project, name="H1", code="H1"
        )
        ProdocWaveSite.objects.create(wave=wave, site=site)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProdocWaveSite.objects.create(wave=wave, site=site)
