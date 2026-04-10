"""Serializer for ProdocSite (project-scoped)."""

from rest_framework import serializers

from plane.prodoc.models import ProdocSite


class ProdocSiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProdocSite
        fields = [
            "id",
            "workspace",
            "project",
            "name",
            "code",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "workspace",
            "project",
            "created_at",
            "updated_at",
        ]
