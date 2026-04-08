"""Serializers for materialization: request body, dry-run response, job row.

The dry-run response mirrors the `Plan` dataclass structure from
`plane.prodoc.materialization.plan`. We don't use DRF serializers to
*read* the plan — it's a dataclass, not a model — so there's a thin
`plan_to_dict` helper that renders a Plan as a JSON-safe dict. Keeping
the projection here (rather than in the view) means the shape is
documented in one place and can evolve without touching the view.
"""

from rest_framework import serializers

from plane.prodoc.models import ProdocMaterializationJob


class MaterializeRequestSerializer(serializers.Serializer):
    template_slug = serializers.SlugField(max_length=120)
    version = serializers.CharField(max_length=20)
    start_date = serializers.DateField()
    dry_run = serializers.BooleanField(default=False)


class ProdocMaterializationJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProdocMaterializationJob
        fields = [
            "id",
            "workspace",
            "project",
            "template",
            "status",
            "start_date",
            "error_log",
            "work_items_created",
            "modules_created",
            "relations_created",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


def plan_to_dict(plan):
    """Render a materialization `Plan` dataclass as a JSON-safe dict.

    Used by the dry-run endpoint to return the full expansion tree in
    the response body without touching the database. Work items are
    serialized in plan order (stable — planner never reorders).
    Relations reference work items by integer index into the returned
    `work_items` list, matching `PlannedRelation.upstream_index` /
    `downstream_index` exactly.
    """
    return {
        "template_id": str(plan.template_id),
        "project_id": str(plan.project_id),
        "workspace_id": str(plan.workspace_id),
        "start_date": plan.start_date.isoformat(),
        "module_specs": [
            {
                "wave_id": str(spec["wave_id"]),
                "name": spec["name"],
                "existing_module_id": (
                    str(spec["existing_module_id"])
                    if spec.get("existing_module_id")
                    else None
                ),
            }
            for spec in plan.module_specs
        ],
        "work_items": [
            {
                "template_task_id": str(wi.template_task_id),
                "template_task_slug": wi.template_task_slug,
                "title": wi.title,
                "description": wi.description,
                "start_date": wi.start_date.isoformat(),
                "target_date": wi.target_date.isoformat(),
                "role_key": wi.role_key,
                "sla_hours": wi.sla_hours,
                "wave_id": str(wi.wave_id) if wi.wave_id else None,
                "wave_name": wi.wave_name,
                "site_id": str(wi.site_id) if wi.site_id else None,
                "site_code": wi.site_code,
                "migration_requirement_ids": [
                    str(x) for x in wi.migration_requirement_ids
                ],
                "third_party_tool_ids": [
                    str(x) for x in wi.third_party_tool_ids
                ],
            }
            for wi in plan.work_items
        ],
        "relations": [
            {
                "upstream_index": rel.upstream_index,
                "downstream_index": rel.downstream_index,
            }
            for rel in plan.relations
        ],
        "warnings": list(plan.warnings),
    }
