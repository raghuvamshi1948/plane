# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Idempotent seed command for a Prodoc template + reference data.

Usage:
    python manage.py seed_prodoc_template \
        --workspace=<slug> \
        --file=path/to/template.json

Expected JSON shape:

    {
      "template": {"slug": "mgm", "version": "1.0", "name": "...",
                   "description": "..."},
      "migration_requirements": [
        {"slug": "req-export", "name": "...", "description": "...",
         "category": "data", "default_owner_role": "admin"},
        ...
      ],
      "third_party_tools": [
        {"slug": "tool-foo", ...},
        ...
      ],
      "sections": [
        {"slug": "kickoff", "name": "Kickoff", "order": 1},
        ...
      ],
      "tasks": [
        {"slug": "prep", "section_slug": "kickoff", "title": "...",
         "description": "...", "offset_days": 0, "duration_days": 2,
         "role_key": "admin", "sla_hours": null, "repeat_per_site": false,
         "repeat_per_wave": false, "dependency_mode": "all", "order": 1,
         "migration_requirement_slugs": ["req-export"],
         "third_party_tool_slugs": []},
        ...
      ],
      "dependencies": [
        {"upstream_slug": "prep", "downstream_slug": "launch"},
        ...
      ]
    }

Idempotency contract (plan file, commit 10):
  - Templates are keyed by (workspace, slug, version). Re-running
    the same file is a no-op on the template row if it already exists
    at the same version. Mutable fields (name, description) are
    refreshed only if the template is NOT yet locked.
  - Reference data is keyed by (workspace, slug) and always upserted
    in place — reference catalogs are meant to evolve independently
    of template versions.
  - Sections, tasks, and dependencies are fully rebuilt from the file
    on every run for an unlocked template. A locked template is
    skipped with a warning: bump the version in the JSON to edit.
  - The whole import runs inside transaction.atomic() so a partial
    failure leaves the DB untouched.
"""

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from plane.db.models import Workspace
from plane.prodoc.models import (
    ProdocMigrationRequirement,
    ProdocTemplate,
    ProdocTemplateSection,
    ProdocTemplateTask,
    ProdocTemplateTaskDependency,
    ProdocThirdPartyTool,
)


class Command(BaseCommand):
    help = "Seed (or refresh) a Prodoc template from a JSON document."

    def add_arguments(self, parser):
        parser.add_argument(
            "--workspace",
            required=True,
            help="Target workspace slug.",
        )
        parser.add_argument(
            "--file",
            required=True,
            help="Path to the template JSON document.",
        )

    def handle(self, *args, **options):
        slug = options["workspace"]
        path = options["file"]

        try:
            workspace = Workspace.objects.get(slug=slug)
        except Workspace.DoesNotExist:
            raise CommandError(f"Workspace '{slug}' not found")

        try:
            with open(path) as f:
                doc = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"Seed file '{path}' not found")
        except json.JSONDecodeError as e:
            raise CommandError(f"Seed file '{path}' is not valid JSON: {e}")

        with transaction.atomic():
            self._seed_reference_data(workspace, doc)
            template = self._seed_template(workspace, doc)
            if template is None:
                return
            self._seed_sections_tasks_deps(template, doc)

    # ------------------------------------------------------------------
    # Reference data — always upsert by (workspace, slug).
    # ------------------------------------------------------------------
    def _seed_reference_data(self, workspace, doc):
        for row in doc.get("migration_requirements", []):
            obj, created = ProdocMigrationRequirement.objects.update_or_create(
                workspace=workspace,
                slug=row["slug"],
                defaults={
                    "name": row["name"],
                    "description": row.get("description", ""),
                    "category": row["category"],
                    "default_owner_role": row["default_owner_role"],
                },
            )
            verb = "created" if created else "updated"
            self.stdout.write(f"  migration_requirement {row['slug']} {verb}")

        for row in doc.get("third_party_tools", []):
            obj, created = ProdocThirdPartyTool.objects.update_or_create(
                workspace=workspace,
                slug=row["slug"],
                defaults={
                    "name": row["name"],
                    "description": row.get("description", ""),
                    "category": row["category"],
                    "default_owner_role": row["default_owner_role"],
                },
            )
            verb = "created" if created else "updated"
            self.stdout.write(f"  third_party_tool {row['slug']} {verb}")

    # ------------------------------------------------------------------
    # Template — keyed by (workspace, slug, version). Locked templates
    # at the same version are skipped with a warning: the operator must
    # bump the version to edit.
    # ------------------------------------------------------------------
    def _seed_template(self, workspace, doc):
        tpl_doc = doc["template"]
        try:
            template = ProdocTemplate.objects.get(
                workspace=workspace,
                slug=tpl_doc["slug"],
                version=tpl_doc["version"],
                deleted_at__isnull=True,
            )
            if template.is_locked:
                self.stdout.write(
                    self.style.WARNING(
                        f"template {tpl_doc['slug']}@{tpl_doc['version']} "
                        f"is locked — skipping. Bump the version to edit."
                    )
                )
                return None
            template.name = tpl_doc["name"]
            template.description = tpl_doc.get("description", "")
            template.save(update_fields=["name", "description", "updated_at"])
            self.stdout.write(
                f"  template {tpl_doc['slug']}@{tpl_doc['version']} updated"
            )
        except ProdocTemplate.DoesNotExist:
            template = ProdocTemplate.objects.create(
                workspace=workspace,
                slug=tpl_doc["slug"],
                version=tpl_doc["version"],
                name=tpl_doc["name"],
                description=tpl_doc.get("description", ""),
            )
            self.stdout.write(
                f"  template {tpl_doc['slug']}@{tpl_doc['version']} created"
            )
        return template

    # ------------------------------------------------------------------
    # Sections + tasks + dependencies — rebuilt from the file on every
    # run for an unlocked template.
    # ------------------------------------------------------------------
    def _seed_sections_tasks_deps(self, template, doc):
        # Wipe existing children (hard delete is fine here — we own
        # every row under an unlocked template, and the soft-delete
        # cascade isn't useful at seed time).
        ProdocTemplateTaskDependency.all_objects.filter(
            upstream__template=template
        ).delete()
        ProdocTemplateTask.all_objects.filter(template=template).delete()
        ProdocTemplateSection.all_objects.filter(template=template).delete()

        sections_by_slug = {}
        for row in doc.get("sections", []):
            section = ProdocTemplateSection.objects.create(
                template=template,
                name=row["name"],
                order=row["order"],
            )
            sections_by_slug[row["slug"]] = section

        tasks_by_slug = {}
        for row in doc.get("tasks", []):
            section = sections_by_slug.get(row["section_slug"])
            if section is None:
                raise CommandError(
                    f"task '{row['slug']}' references unknown section "
                    f"'{row['section_slug']}'"
                )
            task = ProdocTemplateTask.objects.create(
                template=template,
                section=section,
                slug=row["slug"],
                title=row["title"],
                description=row.get("description", ""),
                offset_days=row["offset_days"],
                duration_days=row["duration_days"],
                role_key=row["role_key"],
                sla_hours=row.get("sla_hours"),
                repeat_per_site=row.get("repeat_per_site", False),
                repeat_per_wave=row.get("repeat_per_wave", False),
                dependency_mode=row.get("dependency_mode", "all"),
                order=row["order"],
                migration_requirement_slugs=row.get(
                    "migration_requirement_slugs", []
                ),
                third_party_tool_slugs=row.get("third_party_tool_slugs", []),
            )
            tasks_by_slug[row["slug"]] = task

        for row in doc.get("dependencies", []):
            up = tasks_by_slug.get(row["upstream_slug"])
            down = tasks_by_slug.get(row["downstream_slug"])
            if up is None or down is None:
                raise CommandError(
                    f"dependency references unknown task: "
                    f"{row['upstream_slug']} → {row['downstream_slug']}"
                )
            ProdocTemplateTaskDependency.objects.create(
                upstream=up, downstream=down
            )

        self.stdout.write(
            f"  {len(sections_by_slug)} sections, "
            f"{len(tasks_by_slug)} tasks, "
            f"{len(doc.get('dependencies', []))} dependencies"
        )
