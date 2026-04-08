"""
ProdocSite REST endpoints (project-scoped).

Mounted under
  /api/v1/prodoc/workspaces/<slug>/projects/<project_id>/sites/

Sites are per-project (build plan §7.1 decision) — a Hospital in
Project A is a separate row from the same Hospital in Project B. This
keeps template materialization self-contained per project and avoids
cross-project rename/merge complexity that has no customer demand.
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView
from plane.db.models import Project
from plane.prodoc.models import ProdocSite
from plane.prodoc.permissions import ProdocProjectEntityPermission
from plane.prodoc.serializers.site import ProdocSiteSerializer
from plane.prodoc.views.base import ProdocFeatureFlagMixin


def _project(slug, project_id):
    return get_object_or_404(
        Project, pk=project_id, workspace__slug=slug, deleted_at__isnull=True
    )


class ProdocSiteListCreateAPIEndpoint(ProdocFeatureFlagMixin, BaseAPIView):
    permission_classes = [ProdocProjectEntityPermission]
    use_read_replica = False

    def get(self, request, slug, project_id):
        project = _project(slug, project_id)
        qs = ProdocSite.objects.filter(
            project=project, deleted_at__isnull=True
        ).order_by("code")
        return Response(
            ProdocSiteSerializer(qs, many=True).data, status=status.HTTP_200_OK
        )

    def post(self, request, slug, project_id):
        project = _project(slug, project_id)
        serializer = ProdocSiteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            workspace=project.workspace,
            project=project,
            created_by=request.user,
            updated_by=request.user,
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProdocSiteDetailAPIEndpoint(ProdocFeatureFlagMixin, BaseAPIView):
    permission_classes = [ProdocProjectEntityPermission]
    use_read_replica = False

    def _get(self, slug, project_id, site_id):
        return get_object_or_404(
            ProdocSite,
            pk=site_id,
            project_id=project_id,
            project__workspace__slug=slug,
            deleted_at__isnull=True,
        )

    def get(self, request, slug, project_id, site_id):
        site = self._get(slug, project_id, site_id)
        return Response(
            ProdocSiteSerializer(site).data, status=status.HTTP_200_OK
        )

    def patch(self, request, slug, project_id, site_id):
        site = self._get(slug, project_id, site_id)
        serializer = ProdocSiteSerializer(site, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, slug, project_id, site_id):
        site = self._get(slug, project_id, site_id)
        site.deleted_at = timezone.now()
        site.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
