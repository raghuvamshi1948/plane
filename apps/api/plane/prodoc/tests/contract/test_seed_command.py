# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Tests for the seed_prodoc_template management command.

Verifies the idempotency contract from the plan file (commit 10):
  - First run creates rows.
  - Second run with the same file is a no-op that does not bump
    created_at on the template row.
  - Bumping the version in the JSON creates a new template alongside
    the old one; reference data is upserted in place.
  - A locked template is skipped with a warning — no edits at the same
    version.
"""

import io
import json
import pathlib

import pytest
from django.core.management import call_command

from plane.prodoc.models import (
    ProdocMigrationRequirement,
    ProdocTemplate,
    ProdocTemplateSection,
    ProdocTemplateTask,
    ProdocTemplateTaskDependency,
    ProdocThirdPartyTool,
)


SEED_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "seeds"
    / "mgm_phase1.json"
)


def _run_seed(workspace_slug, path=None):
    out = io.StringIO()
    call_command(
        "seed_prodoc_template",
        f"--workspace={workspace_slug}",
        f"--file={path or SEED_PATH}",
        stdout=out,
    )
    return out.getvalue()


def _write_variant(tmp_path, mutator):
    """Load the canonical seed, mutate it, write to tmp, return the path."""
    with open(SEED_PATH) as f:
        doc = json.load(f)
    mutator(doc)
    out = tmp_path / "variant.json"
    out.write_text(json.dumps(doc))
    return out


@pytest.mark.contract
class TestSeedCommand:
    @pytest.mark.django_db
    def test_first_run_creates_rows(self, workspace):
        _run_seed(workspace.slug)

        assert ProdocTemplate.objects.filter(
            workspace=workspace, slug="mgm-phase1", version="1.0"
        ).count() == 1
        template = ProdocTemplate.objects.get(
            workspace=workspace, slug="mgm-phase1"
        )
        assert ProdocTemplateSection.objects.filter(template=template).count() == 2
        assert ProdocTemplateTask.objects.filter(template=template).count() == 3
        assert (
            ProdocTemplateTaskDependency.objects.filter(
                upstream__template=template
            ).count()
            == 2
        )
        assert (
            ProdocMigrationRequirement.objects.filter(workspace=workspace).count()
            == 2
        )
        assert (
            ProdocThirdPartyTool.objects.filter(workspace=workspace).count() == 1
        )

    @pytest.mark.django_db
    def test_second_run_is_noop_on_template(self, workspace):
        _run_seed(workspace.slug)
        template = ProdocTemplate.objects.get(
            workspace=workspace, slug="mgm-phase1"
        )
        created_at_before = template.created_at

        _run_seed(workspace.slug)

        template.refresh_from_db()
        # created_at must not change on the second run.
        assert template.created_at == created_at_before
        # Counts stay exactly the same.
        assert ProdocTemplateTask.objects.filter(template=template).count() == 3
        assert (
            ProdocMigrationRequirement.objects.filter(workspace=workspace).count()
            == 2
        )

    @pytest.mark.django_db
    def test_bumping_version_creates_new_template_row(
        self, workspace, tmp_path
    ):
        _run_seed(workspace.slug)
        variant = _write_variant(
            tmp_path, lambda d: d["template"].update({"version": "2.0"})
        )
        _run_seed(workspace.slug, path=variant)

        # Both versions exist side-by-side.
        versions = set(
            ProdocTemplate.objects.filter(
                workspace=workspace, slug="mgm-phase1"
            ).values_list("version", flat=True)
        )
        assert versions == {"1.0", "2.0"}

    @pytest.mark.django_db
    def test_locked_template_is_skipped_with_warning(
        self, workspace, tmp_path
    ):
        _run_seed(workspace.slug)
        template = ProdocTemplate.objects.get(
            workspace=workspace, slug="mgm-phase1"
        )
        template.is_locked = True
        template.save(update_fields=["is_locked"])

        variant = _write_variant(
            tmp_path,
            lambda d: d["template"].update({"name": "Would Overwrite"}),
        )
        output = _run_seed(workspace.slug, path=variant)

        assert "locked" in output.lower()
        template.refresh_from_db()
        # Name was NOT rewritten because the template is locked.
        assert template.name != "Would Overwrite"
