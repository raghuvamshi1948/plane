"""
Serializer for ProdocProjectSettings.

The only writable field today is `holiday_calendar`. Validation enforces
that the chosen calendar belongs to the same workspace as the project,
so a workspace can never reference another workspace's calendar through
the override (CLAUDE.md §3 — workspace is the tenant boundary).
"""

from rest_framework import serializers

from plane.prodoc.models import HolidayCalendar, ProdocProjectSettings


class ProdocProjectSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProdocProjectSettings
        fields = [
            "id",
            "project",
            "holiday_calendar",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "project",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]

    def validate_holiday_calendar(self, value):
        if value is None:
            return value
        # The view passes the project (or its workspace_id) into context
        # so we can enforce same-workspace ownership without re-querying.
        workspace_id = self.context.get("workspace_id")
        if workspace_id is None:
            raise serializers.ValidationError(
                "Internal error: serializer context missing workspace_id."
            )
        if str(value.workspace_id) != str(workspace_id):
            raise serializers.ValidationError(
                "holiday_calendar must belong to the same workspace as the project."
            )
        return value
