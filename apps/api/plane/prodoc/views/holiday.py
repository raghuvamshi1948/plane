"""
HolidayCalendar REST endpoints.

Mounted under /api/v1/prodoc/workspaces/<slug>/holiday-calendars/.

Auth: X-API-Key (inherited from BaseAPIView).
Permissions: ProdocWorkspaceEntityPermission — same workspace-membership
contract as upstream's WorkspaceEntityPermission, with the Prodoc-side
seam for future tightening.
Feature flag: ProdocFeatureFlagMixin returns 404 when PRODOC_FEATURES_ENABLED
is not "1".

Soft-delete per CLAUDE.md §5: DELETE sets `deleted_at` rather than
removing the row, and every queryset filters `deleted_at__isnull=True`.
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView
from plane.db.models import Workspace
from plane.prodoc.models import HolidayCalendar
from plane.prodoc.permissions import ProdocWorkspaceEntityPermission
from plane.prodoc.serializers.holiday import HolidayCalendarSerializer
from plane.prodoc.views.base import ProdocFeatureFlagMixin


class HolidayCalendarListCreateAPIEndpoint(ProdocFeatureFlagMixin, BaseAPIView):
    """GET (list) and POST (create) for HolidayCalendar in a workspace."""

    permission_classes = [ProdocWorkspaceEntityPermission]
    use_read_replica = False

    def _workspace(self, slug):
        return get_object_or_404(Workspace, slug=slug)

    def get(self, request, slug):
        workspace = self._workspace(slug)
        # Workspace-scoped per CLAUDE.md §3: every queryset starts with
        # the tenant filter.
        qs = HolidayCalendar.objects.filter(
            workspace=workspace,
            deleted_at__isnull=True,
        ).order_by("name")
        serializer = HolidayCalendarSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, slug):
        workspace = self._workspace(slug)
        serializer = HolidayCalendarSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            workspace=workspace,
            created_by=request.user,
            updated_by=request.user,
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class HolidayCalendarDetailAPIEndpoint(ProdocFeatureFlagMixin, BaseAPIView):
    """GET, PATCH, DELETE for a single HolidayCalendar."""

    permission_classes = [ProdocWorkspaceEntityPermission]
    use_read_replica = False

    def _get_object(self, slug, pk):
        # Workspace filter is in the lookup, not just the permission
        # class — defense in depth.
        return get_object_or_404(
            HolidayCalendar,
            pk=pk,
            workspace__slug=slug,
            deleted_at__isnull=True,
        )

    def get(self, request, slug, pk):
        calendar = self._get_object(slug, pk)
        return Response(HolidayCalendarSerializer(calendar).data, status=status.HTTP_200_OK)

    def patch(self, request, slug, pk):
        calendar = self._get_object(slug, pk)
        serializer = HolidayCalendarSerializer(calendar, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, slug, pk):
        calendar = self._get_object(slug, pk)
        # Soft-delete per CLAUDE.md §5.
        calendar.deleted_at = timezone.now()
        calendar.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
