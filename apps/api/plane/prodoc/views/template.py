"""
ProdocTemplate REST endpoints (templates, sections, tasks, dependencies).

All routes mount under `/api/v1/prodoc/workspaces/<slug>/templates/...`.

Workspace + feature-flag gating is handled by
`ProdocWorkspaceEntityPermission` + `ProdocFeatureFlagMixin`. Every
queryset starts with the workspace filter per CLAUDE.md §3, and object
lookups repeat the filter rather than relying on the permission class
alone — defense in depth.

Locked templates:
    Once a template is materialized, `is_locked=True` and PATCH returns
    409. Section/task/dependency edits *also* refuse on locked
    templates — the whole tree is immutable after first use, and the
    only way forward is to bump the version and create a new root.

Dependency cycles:
    The dependency-create endpoint runs a DFS over the existing
    dependency graph before saving. A new edge u→d is rejected if `d`
    already transitively reaches `u`. The serializer can't do this
    (needs the full graph), so it lives in the view.
"""

from django.db import models
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView
from plane.db.models import Workspace
from plane.prodoc.models import (
    ProdocTemplate,
    ProdocTemplateSection,
    ProdocTemplateTask,
    ProdocTemplateTaskDependency,
)
from plane.prodoc.permissions import ProdocWorkspaceEntityPermission
from plane.prodoc.serializers.template import (
    ProdocTemplateSectionSerializer,
    ProdocTemplateSerializer,
    ProdocTemplateTaskDependencySerializer,
    ProdocTemplateTaskSerializer,
)
from plane.prodoc.views.base import ProdocFeatureFlagMixin


def _workspace(slug):
    return get_object_or_404(Workspace, slug=slug)


def _get_template(slug, template_id):
    return get_object_or_404(
        ProdocTemplate,
        pk=template_id,
        workspace__slug=slug,
        deleted_at__isnull=True,
    )


def _locked_response():
    return Response(
        {
            "error": (
                "Template is locked. Bump the version and create a new "
                "template to apply changes."
            )
        },
        status=status.HTTP_409_CONFLICT,
    )


# ---------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------


class ProdocTemplateListCreateAPIEndpoint(ProdocFeatureFlagMixin, BaseAPIView):
    permission_classes = [ProdocWorkspaceEntityPermission]
    use_read_replica = False

    def get(self, request, slug):
        workspace = _workspace(slug)
        qs = ProdocTemplate.objects.filter(
            workspace=workspace, deleted_at__isnull=True
        ).order_by("slug", "-version")
        return Response(
            ProdocTemplateSerializer(qs, many=True).data,
            status=status.HTTP_200_OK,
        )

    def post(self, request, slug):
        workspace = _workspace(slug)
        serializer = ProdocTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            workspace=workspace,
            created_by=request.user,
            updated_by=request.user,
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProdocTemplateDetailAPIEndpoint(ProdocFeatureFlagMixin, BaseAPIView):
    permission_classes = [ProdocWorkspaceEntityPermission]
    use_read_replica = False

    def get(self, request, slug, template_id):
        template = _get_template(slug, template_id)
        return Response(
            ProdocTemplateSerializer(template).data, status=status.HTTP_200_OK
        )

    def patch(self, request, slug, template_id):
        template = _get_template(slug, template_id)
        if template.is_locked:
            return _locked_response()
        serializer = ProdocTemplateSerializer(
            template, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, slug, template_id):
        template = _get_template(slug, template_id)
        template.deleted_at = timezone.now()
        template.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------


class ProdocTemplateSectionListCreateAPIEndpoint(
    ProdocFeatureFlagMixin, BaseAPIView
):
    permission_classes = [ProdocWorkspaceEntityPermission]
    use_read_replica = False

    def get(self, request, slug, template_id):
        template = _get_template(slug, template_id)
        qs = ProdocTemplateSection.objects.filter(
            template=template, deleted_at__isnull=True
        ).order_by("order")
        return Response(
            ProdocTemplateSectionSerializer(qs, many=True).data,
            status=status.HTTP_200_OK,
        )

    def post(self, request, slug, template_id):
        template = _get_template(slug, template_id)
        if template.is_locked:
            return _locked_response()
        serializer = ProdocTemplateSectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            template=template,
            created_by=request.user,
            updated_by=request.user,
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProdocTemplateSectionDetailAPIEndpoint(
    ProdocFeatureFlagMixin, BaseAPIView
):
    permission_classes = [ProdocWorkspaceEntityPermission]
    use_read_replica = False

    def _get(self, slug, template_id, section_id):
        return get_object_or_404(
            ProdocTemplateSection,
            pk=section_id,
            template_id=template_id,
            template__workspace__slug=slug,
            deleted_at__isnull=True,
        )

    def get(self, request, slug, template_id, section_id):
        section = self._get(slug, template_id, section_id)
        return Response(
            ProdocTemplateSectionSerializer(section).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, slug, template_id, section_id):
        section = self._get(slug, template_id, section_id)
        if section.template.is_locked:
            return _locked_response()
        serializer = ProdocTemplateSectionSerializer(
            section, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, slug, template_id, section_id):
        section = self._get(slug, template_id, section_id)
        if section.template.is_locked:
            return _locked_response()
        section.deleted_at = timezone.now()
        section.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------


class ProdocTemplateTaskListCreateAPIEndpoint(
    ProdocFeatureFlagMixin, BaseAPIView
):
    permission_classes = [ProdocWorkspaceEntityPermission]
    use_read_replica = False

    def get(self, request, slug, template_id):
        template = _get_template(slug, template_id)
        qs = ProdocTemplateTask.objects.filter(
            template=template, deleted_at__isnull=True
        ).order_by("order")
        return Response(
            ProdocTemplateTaskSerializer(qs, many=True).data,
            status=status.HTTP_200_OK,
        )

    def post(self, request, slug, template_id):
        template = _get_template(slug, template_id)
        if template.is_locked:
            return _locked_response()
        section_id = request.data.get("section")
        section = get_object_or_404(
            ProdocTemplateSection,
            pk=section_id,
            template=template,
            deleted_at__isnull=True,
        )
        serializer = ProdocTemplateTaskSerializer(
            data=request.data,
            context={"workspace": template.workspace},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(
            template=template,
            section=section,
            created_by=request.user,
            updated_by=request.user,
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProdocTemplateTaskDetailAPIEndpoint(ProdocFeatureFlagMixin, BaseAPIView):
    permission_classes = [ProdocWorkspaceEntityPermission]
    use_read_replica = False

    def _get(self, slug, template_id, task_id):
        return get_object_or_404(
            ProdocTemplateTask,
            pk=task_id,
            template_id=template_id,
            template__workspace__slug=slug,
            deleted_at__isnull=True,
        )

    def get(self, request, slug, template_id, task_id):
        task = self._get(slug, template_id, task_id)
        return Response(
            ProdocTemplateTaskSerializer(task).data, status=status.HTTP_200_OK
        )

    def patch(self, request, slug, template_id, task_id):
        task = self._get(slug, template_id, task_id)
        if task.template.is_locked:
            return _locked_response()
        serializer = ProdocTemplateTaskSerializer(
            task,
            data=request.data,
            partial=True,
            context={"workspace": task.template.workspace},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, slug, template_id, task_id):
        task = self._get(slug, template_id, task_id)
        if task.template.is_locked:
            return _locked_response()
        task.deleted_at = timezone.now()
        task.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------


def _would_create_cycle(template_id, upstream_id, downstream_id):
    """DFS over existing dependencies to detect cycles before insert.

    A new edge u→d creates a cycle if `u` is already reachable from `d`
    through the existing graph. We load only the template's edges and
    walk forward from `d`.
    """
    edges = list(
        ProdocTemplateTaskDependency.objects.filter(
            upstream__template_id=template_id,
            deleted_at__isnull=True,
        ).values_list("upstream_id", "downstream_id")
    )
    adjacency = {}
    for up, dn in edges:
        adjacency.setdefault(up, []).append(dn)

    # Walk forward from downstream: if we reach upstream, a cycle exists.
    stack = [downstream_id]
    visited = set()
    while stack:
        node = stack.pop()
        if node == upstream_id:
            return True
        if node in visited:
            continue
        visited.add(node)
        stack.extend(adjacency.get(node, []))
    return False


class ProdocTemplateTaskDependencyListCreateAPIEndpoint(
    ProdocFeatureFlagMixin, BaseAPIView
):
    permission_classes = [ProdocWorkspaceEntityPermission]
    use_read_replica = False

    def get(self, request, slug, template_id):
        template = _get_template(slug, template_id)
        qs = ProdocTemplateTaskDependency.objects.filter(
            upstream__template=template, deleted_at__isnull=True
        ).order_by("created_at")
        return Response(
            ProdocTemplateTaskDependencySerializer(qs, many=True).data,
            status=status.HTTP_200_OK,
        )

    def post(self, request, slug, template_id):
        template = _get_template(slug, template_id)
        if template.is_locked:
            return _locked_response()
        serializer = ProdocTemplateTaskDependencySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upstream = serializer.validated_data["upstream"]
        downstream = serializer.validated_data["downstream"]
        if upstream.template_id != template.id or downstream.template_id != template.id:
            return Response(
                {"error": "tasks must belong to this template"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if _would_create_cycle(template.id, upstream.id, downstream.id):
            return Response(
                {"error": "dependency would create a cycle"},
                status=status.HTTP_409_CONFLICT,
            )
        serializer.save(created_by=request.user, updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProdocTemplateTaskDependencyDetailAPIEndpoint(
    ProdocFeatureFlagMixin, BaseAPIView
):
    permission_classes = [ProdocWorkspaceEntityPermission]
    use_read_replica = False

    def delete(self, request, slug, template_id, dependency_id):
        dep = get_object_or_404(
            ProdocTemplateTaskDependency,
            pk=dependency_id,
            upstream__template_id=template_id,
            upstream__template__workspace__slug=slug,
            deleted_at__isnull=True,
        )
        if dep.upstream.template.is_locked:
            return _locked_response()
        dep.deleted_at = timezone.now()
        dep.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
