"""
Serializers for ProdocTemplate, ProdocTemplateSection, ProdocTemplateTask,
and ProdocTemplateTaskDependency.

Workspace ownership is stamped at `save()` from serializer context — the
workspace is taken from the viewset's URL kwarg, never from the request
body. This matches CLAUDE.md §3: tenant isolation is enforced in
Python, and we never trust a client-supplied workspace id.

The task serializer validates `migration_requirement_slugs` and
`third_party_tool_slugs` at write time against the workspace's catalog,
so a misspelled slug surfaces as a 400 at template edit time rather
than a 422 at materialize time.

Cycle detection on dependencies is intentionally done by the *view*,
not the serializer. A serializer runs in isolation for a single row,
but detecting a cycle requires loading the full graph. The view
performs a DFS before saving — see `ProdocTemplateTaskDependencyListCreateAPIEndpoint`.
"""

from rest_framework import serializers

from plane.prodoc.models import (
    ProdocMigrationRequirement,
    ProdocTemplate,
    ProdocTemplateSection,
    ProdocTemplateTask,
    ProdocTemplateTaskDependency,
    ProdocThirdPartyTool,
)


class ProdocTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProdocTemplate
        fields = [
            "id",
            "workspace",
            "slug",
            "version",
            "name",
            "description",
            "is_locked",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "workspace",
            "is_locked",
            "created_at",
            "updated_at",
        ]


class ProdocTemplateSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProdocTemplateSection
        fields = [
            "id",
            "template",
            "name",
            "order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "template", "created_at", "updated_at"]


class ProdocTemplateTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProdocTemplateTask
        fields = [
            "id",
            "template",
            "section",
            "slug",
            "title",
            "description",
            "offset_days",
            "duration_days",
            "role_key",
            "sla_hours",
            "repeat_per_site",
            "repeat_per_wave",
            "dependency_mode",
            "order",
            "migration_requirement_slugs",
            "third_party_tool_slugs",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "template", "created_at", "updated_at"]

    def _workspace(self):
        # Viewset stashes the resolved workspace in serializer context so
        # slug validation runs against the right tenant catalog.
        return self.context.get("workspace")

    def _validate_slug_list(self, value, model, field_name):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError(
                {field_name: "must be a list of slug strings."}
            )
        for entry in value:
            if not isinstance(entry, str) or not entry:
                raise serializers.ValidationError(
                    {field_name: f"invalid slug {entry!r}; must be a non-empty string."}
                )
        workspace = self._workspace()
        if workspace is None:
            # Safety net: if the viewset forgot to stash the workspace
            # we refuse rather than silently bypass validation.
            raise serializers.ValidationError(
                {field_name: "workspace context missing; cannot validate."}
            )
        existing = set(
            model.objects.filter(
                workspace=workspace, slug__in=value, deleted_at__isnull=True
            ).values_list("slug", flat=True)
        )
        missing = [s for s in value if s not in existing]
        if missing:
            raise serializers.ValidationError(
                {field_name: f"unknown slugs: {missing}"}
            )
        return value

    def validate_migration_requirement_slugs(self, value):
        return self._validate_slug_list(
            value, ProdocMigrationRequirement, "migration_requirement_slugs"
        )

    def validate_third_party_tool_slugs(self, value):
        return self._validate_slug_list(
            value, ProdocThirdPartyTool, "third_party_tool_slugs"
        )


class ProdocTemplateTaskDependencySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProdocTemplateTaskDependency
        fields = [
            "id",
            "upstream",
            "downstream",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        if attrs["upstream"].id == attrs["downstream"].id:
            raise serializers.ValidationError(
                "upstream and downstream must differ."
            )
        if attrs["upstream"].template_id != attrs["downstream"].template_id:
            raise serializers.ValidationError(
                "upstream and downstream must belong to the same template."
            )
        return attrs
