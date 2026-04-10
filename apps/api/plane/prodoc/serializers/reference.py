"""
Serializers for ProdocMigrationRequirement and ProdocThirdPartyTool.

Both are workspace-scoped reference catalogs. The workspace is stamped
from the viewset URL kwarg, never from the request body — clients
cannot spoof a cross-tenant write.
"""

from rest_framework import serializers

from plane.prodoc.models import ProdocMigrationRequirement, ProdocThirdPartyTool


class ProdocMigrationRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProdocMigrationRequirement
        fields = [
            "id",
            "workspace",
            "slug",
            "name",
            "description",
            "category",
            "default_owner_role",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "workspace", "created_at", "updated_at"]


class ProdocThirdPartyToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProdocThirdPartyTool
        fields = [
            "id",
            "workspace",
            "slug",
            "name",
            "description",
            "category",
            "default_owner_role",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "workspace", "created_at", "updated_at"]
