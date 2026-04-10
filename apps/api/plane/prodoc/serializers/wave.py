"""Serializers for ProdocWave and the wave→site attach endpoint.

The wave→Module mirror is created by the view inside a single atomic
block, not by this serializer — the serializer can't open transactions
and the Module create is a side effect that sits alongside the wave
create, not inside it.
"""

from rest_framework import serializers

from plane.prodoc.models import ProdocWave, ProdocWaveSite


class ProdocWaveSerializer(serializers.ModelSerializer):
    plane_module_id = serializers.PrimaryKeyRelatedField(
        source="plane_module", read_only=True
    )

    class Meta:
        model = ProdocWave
        fields = [
            "id",
            "workspace",
            "project",
            "name",
            "order",
            "start_offset_days",
            "plane_module_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "workspace",
            "project",
            "plane_module_id",
            "created_at",
            "updated_at",
        ]


class ProdocWaveSiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProdocWaveSite
        fields = ["id", "wave", "site", "created_at"]
        read_only_fields = ["id", "wave", "created_at"]
