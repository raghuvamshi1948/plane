"""
ProdocProjectSettings REST endpoint.

Mounted under
/api/v1/prodoc/workspaces/<slug>/projects/<project_id>/settings/.

A single endpoint exposes GET (read the settings) and PATCH (update
them). The row is auto-created on the first PATCH so callers don't have
to POST a settings row before they can write to it — the upstream
`Project` model has no settings row by default and we don't want every
project to carry a Prodoc-specific row until something is actually set
on it.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView
from plane.db.models import Project
from plane.prodoc.models import ProdocProjectSettings
from plane.prodoc.permissions import ProdocProjectEntityPermission
from plane.prodoc.serializers.project_settings import ProdocProjectSettingsSerializer
from plane.prodoc.views.base import ProdocFeatureFlagMixin


class ProdocProjectSettingsAPIEndpoint(ProdocFeatureFlagMixin, BaseAPIView):
    """GET / PATCH for the per-project Prodoc settings sidecar."""

    permission_classes = [ProdocProjectEntityPermission]
    use_read_replica = False

    def _get_project(self, slug, project_id):
        return get_object_or_404(
            Project,
            pk=project_id,
            workspace__slug=slug,
        )

    def _get_or_none(self, project):
        return ProdocProjectSettings.objects.filter(
            project=project,
            deleted_at__isnull=True,
        ).first()

    def get(self, request, slug, project_id):
        project = self._get_project(slug, project_id)
        settings = self._get_or_none(project)
        if settings is None:
            # No row yet — return an empty representation rather than
            # 404, so clients can render a "no override" state without
            # treating it as an error.
            return Response(
                {
                    "project": str(project.id),
                    "holiday_calendar": None,
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            ProdocProjectSettingsSerializer(settings).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, slug, project_id):
        project = self._get_project(slug, project_id)
        settings = self._get_or_none(project)
        context = {"workspace_id": str(project.workspace_id)}

        if settings is None:
            serializer = ProdocProjectSettingsSerializer(
                data=request.data, context=context
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(
                project=project,
                created_by=request.user,
                updated_by=request.user,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        serializer = ProdocProjectSettingsSerializer(
            settings, data=request.data, partial=True, context=context
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
