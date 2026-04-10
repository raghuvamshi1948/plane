"""
ProdocWave REST endpoints and wave→site attach operations.

Mounted under
  /api/v1/prodoc/workspaces/<slug>/projects/<project_id>/waves/
  .../waves/<wave_id>/sites/        (POST to attach, DELETE to detach)

Wave create also creates the Plane `Module` mirror in the same atomic
block. This matches build plan §7.2: a wave always has a module so
ops can manually attach issues to it even before materialization runs,
and a re-materialization picks up the existing module via
`existing_module_id` rather than creating a duplicate.

Deleting a wave soft-deletes the wave row and leaves the Module intact.
The FK is `SET_NULL`, so the Module survives with its historical
issues. Ops can hard-delete modules via the Plane UI if needed.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView
from plane.db.models import Module, Project
from plane.prodoc.models import ProdocSite, ProdocWave, ProdocWaveSite
from plane.prodoc.permissions import ProdocProjectEntityPermission
from plane.prodoc.serializers.wave import (
    ProdocWaveSerializer,
    ProdocWaveSiteSerializer,
)
from plane.prodoc.views.base import ProdocFeatureFlagMixin


def _project(slug, project_id):
    return get_object_or_404(
        Project, pk=project_id, workspace__slug=slug, deleted_at__isnull=True
    )


class ProdocWaveListCreateAPIEndpoint(ProdocFeatureFlagMixin, BaseAPIView):
    permission_classes = [ProdocProjectEntityPermission]
    use_read_replica = False

    def get(self, request, slug, project_id):
        project = _project(slug, project_id)
        qs = ProdocWave.objects.filter(
            project=project, deleted_at__isnull=True
        ).order_by("order")
        return Response(
            ProdocWaveSerializer(qs, many=True).data, status=status.HTTP_200_OK
        )

    def post(self, request, slug, project_id):
        project = _project(slug, project_id)
        serializer = ProdocWaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Wave create + Module mirror create in one atomic block so a
        # half-created wave never leaks into the DB. If the Module
        # create fails (e.g. name collision) the whole thing rolls back.
        with transaction.atomic():
            module = Module.objects.create(
                name=serializer.validated_data["name"],
                project=project,
                workspace=project.workspace,
            )
            wave = serializer.save(
                workspace=project.workspace,
                project=project,
                plane_module=module,
                created_by=request.user,
                updated_by=request.user,
            )
        return Response(
            ProdocWaveSerializer(wave).data, status=status.HTTP_201_CREATED
        )


class ProdocWaveDetailAPIEndpoint(ProdocFeatureFlagMixin, BaseAPIView):
    permission_classes = [ProdocProjectEntityPermission]
    use_read_replica = False

    def _get(self, slug, project_id, wave_id):
        return get_object_or_404(
            ProdocWave,
            pk=wave_id,
            project_id=project_id,
            project__workspace__slug=slug,
            deleted_at__isnull=True,
        )

    def get(self, request, slug, project_id, wave_id):
        wave = self._get(slug, project_id, wave_id)
        return Response(
            ProdocWaveSerializer(wave).data, status=status.HTTP_200_OK
        )

    def patch(self, request, slug, project_id, wave_id):
        wave = self._get(slug, project_id, wave_id)
        serializer = ProdocWaveSerializer(wave, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, slug, project_id, wave_id):
        wave = self._get(slug, project_id, wave_id)
        # SET_NULL on plane_module means the Module survives — ops can
        # hard-delete via the Plane UI. Wave itself is soft-deleted.
        wave.deleted_at = timezone.now()
        wave.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProdocWaveSiteAttachAPIEndpoint(ProdocFeatureFlagMixin, BaseAPIView):
    permission_classes = [ProdocProjectEntityPermission]
    use_read_replica = False

    def post(self, request, slug, project_id, wave_id):
        wave = get_object_or_404(
            ProdocWave,
            pk=wave_id,
            project_id=project_id,
            project__workspace__slug=slug,
            deleted_at__isnull=True,
        )
        site_id = request.data.get("site")
        site = get_object_or_404(
            ProdocSite,
            pk=site_id,
            project_id=project_id,
            deleted_at__isnull=True,
        )
        rel, created = ProdocWaveSite.objects.get_or_create(
            wave=wave,
            site=site,
            defaults={"created_by": request.user, "updated_by": request.user},
        )
        return Response(
            ProdocWaveSiteSerializer(rel).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ProdocWaveSiteDetachAPIEndpoint(ProdocFeatureFlagMixin, BaseAPIView):
    permission_classes = [ProdocProjectEntityPermission]
    use_read_replica = False

    def delete(self, request, slug, project_id, wave_id, site_id):
        rel = get_object_or_404(
            ProdocWaveSite,
            wave_id=wave_id,
            site_id=site_id,
            wave__project_id=project_id,
            wave__project__workspace__slug=slug,
            deleted_at__isnull=True,
        )
        rel.deleted_at = timezone.now()
        rel.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
