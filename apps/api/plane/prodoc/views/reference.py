"""
ProdocMigrationRequirement and ProdocThirdPartyTool REST endpoints.

Mounted under
  /api/v1/prodoc/workspaces/<slug>/migration-requirements/
  /api/v1/prodoc/workspaces/<slug>/third-party-tools/

Both catalogs are workspace-scoped. The viewset pair for each model is
list+create / get+patch+delete, matching the pattern used by
`HolidayCalendar` in `views/holiday.py`.
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView
from plane.db.models import Workspace
from plane.prodoc.models import ProdocMigrationRequirement, ProdocThirdPartyTool
from plane.prodoc.permissions import ProdocWorkspaceEntityPermission
from plane.prodoc.serializers.reference import (
    ProdocMigrationRequirementSerializer,
    ProdocThirdPartyToolSerializer,
)
from plane.prodoc.views.base import ProdocFeatureFlagMixin


def _workspace(slug):
    return get_object_or_404(Workspace, slug=slug)


def _build_view_pair(model_cls, serializer_cls):
    """Factory producing (list-create, detail) views for a reference model.

    Kept as a factory so the two catalogs don't have 90% duplicated
    classes sitting next to each other — the only thing that varies is
    the model and its serializer.
    """

    class _ListCreate(ProdocFeatureFlagMixin, BaseAPIView):
        permission_classes = [ProdocWorkspaceEntityPermission]
        use_read_replica = False

        def get(self, request, slug):
            workspace = _workspace(slug)
            qs = model_cls.objects.filter(
                workspace=workspace, deleted_at__isnull=True
            ).order_by("slug")
            return Response(
                serializer_cls(qs, many=True).data, status=status.HTTP_200_OK
            )

        def post(self, request, slug):
            workspace = _workspace(slug)
            serializer = serializer_cls(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(
                workspace=workspace,
                created_by=request.user,
                updated_by=request.user,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    class _Detail(ProdocFeatureFlagMixin, BaseAPIView):
        permission_classes = [ProdocWorkspaceEntityPermission]
        use_read_replica = False

        def _get(self, slug, pk):
            return get_object_or_404(
                model_cls,
                pk=pk,
                workspace__slug=slug,
                deleted_at__isnull=True,
            )

        def get(self, request, slug, pk):
            obj = self._get(slug, pk)
            return Response(serializer_cls(obj).data, status=status.HTTP_200_OK)

        def patch(self, request, slug, pk):
            obj = self._get(slug, pk)
            serializer = serializer_cls(obj, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save(updated_by=request.user)
            return Response(serializer.data, status=status.HTTP_200_OK)

        def delete(self, request, slug, pk):
            obj = self._get(slug, pk)
            obj.deleted_at = timezone.now()
            obj.save()
            return Response(status=status.HTTP_204_NO_CONTENT)

    return _ListCreate, _Detail


(
    ProdocMigrationRequirementListCreateAPIEndpoint,
    ProdocMigrationRequirementDetailAPIEndpoint,
) = _build_view_pair(
    ProdocMigrationRequirement, ProdocMigrationRequirementSerializer
)

(
    ProdocThirdPartyToolListCreateAPIEndpoint,
    ProdocThirdPartyToolDetailAPIEndpoint,
) = _build_view_pair(ProdocThirdPartyTool, ProdocThirdPartyToolSerializer)
