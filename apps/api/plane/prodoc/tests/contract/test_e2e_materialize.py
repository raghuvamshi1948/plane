# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""End-to-end materialization test.

Exercises the whole Extension 3 stack:
  - Seed the sample template from the JSON file via the management command.
  - Create sites and waves via the REST API (building wave→site assignments).
  - Call POST /materialize/ and run the Celery task inline.
  - Assert that the expected work items, relations, modules, and issue
    links materialized with the right per-site / per-wave expansion and
    that the template became locked.
"""

import pathlib
from unittest.mock import patch

import pytest
from rest_framework import status

from django.core.management import call_command

from plane.db.models import Issue, IssueRelation, Module
from plane.prodoc.models import (
    ProdocIssueLink,
    ProdocMaterializationJob,
    ProdocSite,
    ProdocTemplate,
    ProdocWave,
    ProdocWaveSite,
)
from plane.prodoc.tasks import prodoc_materialize_project


SEED_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "seeds"
    / "mgm_phase1.json"
)


def _flag_on():
    return patch(
        "plane.prodoc.views.base.get_configuration_value",
        return_value=("1",),
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_end_to_end_materialize_from_seed(
    api_key_client, workspace, project
):
    # --- 1. Seed the template from the sample JSON file. ---
    call_command(
        "seed_prodoc_template",
        f"--workspace={workspace.slug}",
        f"--file={SEED_PATH}",
    )
    template = ProdocTemplate.objects.get(
        workspace=workspace, slug="mgm-phase1"
    )

    # --- 2. Create sites via the REST API. ---
    sites_url = (
        f"/api/v1/prodoc/workspaces/{workspace.slug}"
        f"/projects/{project.id}/sites/"
    )
    with _flag_on():
        for code in ["HOSP-A", "HOSP-B", "HOSP-C"]:
            resp = api_key_client.post(
                sites_url,
                data={"name": code, "code": code},
                format="json",
            )
            assert resp.status_code == status.HTTP_201_CREATED

    # --- 3. Create two waves via the REST API. ---
    waves_url = (
        f"/api/v1/prodoc/workspaces/{workspace.slug}"
        f"/projects/{project.id}/waves/"
    )
    wave_ids = []
    with _flag_on():
        for order, name in enumerate(["Wave 1", "Wave 2"], start=1):
            resp = api_key_client.post(
                waves_url,
                data={
                    "name": name,
                    "order": order,
                    "start_offset_days": (order - 1) * 10,
                },
                format="json",
            )
            assert resp.status_code == status.HTTP_201_CREATED
            wave_ids.append(resp.data["id"])

    # --- 4. Attach sites to waves: Wave 1 = HOSP-A; Wave 2 = HOSP-B, HOSP-C
    sites = list(ProdocSite.objects.filter(project=project).order_by("code"))
    assignments = {
        wave_ids[0]: [sites[0].id],
        wave_ids[1]: [sites[1].id, sites[2].id],
    }
    with _flag_on():
        for wave_id, site_id_list in assignments.items():
            attach_url = (
                f"/api/v1/prodoc/workspaces/{workspace.slug}"
                f"/projects/{project.id}/waves/{wave_id}/sites/"
            )
            for site_id in site_id_list:
                resp = api_key_client.post(
                    attach_url,
                    data={"site": str(site_id)},
                    format="json",
                )
                assert resp.status_code == status.HTTP_201_CREATED

    # --- 5. Kick off materialization (wet run). Run the Celery task
    #        inline so the test stays deterministic without a live broker.
    materialize_url = (
        f"/api/v1/prodoc/workspaces/{workspace.slug}"
        f"/projects/{project.id}/materialize/"
    )

    def _inline(job_id):
        prodoc_materialize_project(job_id)

    with _flag_on(), patch(
        "plane.prodoc.views.materialize.prodoc_materialize_project.delay",
        side_effect=_inline,
    ):
        resp = api_key_client.post(
            materialize_url,
            data={
                "template_slug": "mgm-phase1",
                "version": "1.0",
                "start_date": "2026-04-06",
                "dry_run": False,
            },
            format="json",
        )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    job_id = resp.data["job_id"]

    # --- 6. Assert final state. ---
    job = ProdocMaterializationJob.objects.get(id=job_id)
    assert job.status == "succeeded"

    # Expansion: prep (1) + site-visit (3 per site) + launch (2 per wave)
    # = 1 + 3 + 2 = 6 work items.
    assert Issue.objects.filter(project=project).count() == 6

    # Every work item has a sidecar link carrying template_task + site/wave.
    assert ProdocIssueLink.objects.filter(project=project).count() == 6

    # Two waves → two Plane Modules mirrored.
    assert Module.objects.filter(project=project).count() == 2

    # Dependency edges:
    #   - prep → site-visit: site-visit is the downstream with
    #     dependency_mode="same_site", but prep has no site, so the
    #     wildcard rule makes 1 prep × 3 site-visits = 3 edges.
    #   - site-visit → launch: launch is the downstream with
    #     dependency_mode="all", so every site-visit blocks every
    #     launch = 3 × 2 = 6 edges.
    # Total: 9.
    assert IssueRelation.objects.filter(project=project).count() == 9

    # Template is now locked — a PATCH attempt would 409.
    template.refresh_from_db()
    assert template.is_locked is True

    # Sidecar M2M preserved: `prep` carries two migration requirements
    # and one third-party tool.
    prep_link = ProdocIssueLink.objects.get(
        project=project, template_task__slug="prep"
    )
    assert prep_link.migration_requirements.count() == 2
    assert prep_link.third_party_tools.count() == 1

    # Sites attached to waves are reflected: each wave→site link exists.
    assert ProdocWaveSite.objects.filter(
        wave__project=project, deleted_at__isnull=True
    ).count() == 3
