"""
Materialize + materialization-job REST endpoints.

POST /api/v1/prodoc/projects/<project_id>/materialize/
  Body: {template_slug, version, start_date, dry_run}

Dry-run path is synchronous and writes nothing — it calls
`build_plan` directly and returns the rendered plan tree in the
response body. Zero DB writes, zero Celery dispatch. Callers use
this to preview date math and expansion before committing.

Wet-run path creates a `ProdocMaterializationJob` row, dispatches
`prodoc_materialize_project.delay(job_id)`, and returns 202 with the
job id so the client can poll the job detail endpoint.

Idempotency: a project can only have one `running` or `queued` job at
a time. Re-posting while a job is in flight returns 409 with the
in-flight job id so the caller can poll it instead of racing a
second one.

GET /api/v1/prodoc/projects/<project_id>/materialization-jobs/<job_id>/
  Returns the current job row (status, error_log, created artifact
  counts). Used by clients polling for completion.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView
from plane.db.models import Project
from plane.prodoc.materialization import (
    MaterializationValidationError,
    build_plan,
)
from plane.prodoc.models import (
    ProdocMaterializationJob,
    ProdocSite,
    ProdocTemplate,
    ProdocWave,
)
from plane.prodoc.permissions import ProdocProjectEntityPermission
from plane.prodoc.serializers.materialization import (
    MaterializeRequestSerializer,
    ProdocMaterializationJobSerializer,
    plan_to_dict,
)
from plane.prodoc.tasks import prodoc_materialize_project
from plane.prodoc.views.base import ProdocFeatureFlagMixin


def _project(slug, project_id):
    return get_object_or_404(
        Project, pk=project_id, workspace__slug=slug, deleted_at__isnull=True
    )


class ProdocMaterializeAPIEndpoint(ProdocFeatureFlagMixin, BaseAPIView):
    permission_classes = [ProdocProjectEntityPermission]
    use_read_replica = False

    def post(self, request, slug, project_id):
        project = _project(slug, project_id)
        req = MaterializeRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        template = get_object_or_404(
            ProdocTemplate,
            workspace=project.workspace,
            slug=req.validated_data["template_slug"],
            version=req.validated_data["version"],
            deleted_at__isnull=True,
        )

        sites = list(
            ProdocSite.objects.filter(
                project=project, deleted_at__isnull=True
            )
        )
        waves = list(
            ProdocWave.objects.filter(
                project=project, deleted_at__isnull=True
            ).order_by("order")
        )

        if req.validated_data["dry_run"]:
            try:
                plan = build_plan(
                    template=template,
                    project=project,
                    start_date=req.validated_data["start_date"],
                    sites=sites,
                    waves=waves,
                )
            except MaterializationValidationError as e:
                return Response(
                    {"errors": e.errors},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            return Response(plan_to_dict(plan), status=status.HTTP_200_OK)

        # Wet run: refuse if a job is already in flight for this project.
        in_flight = ProdocMaterializationJob.objects.filter(
            project=project,
            status__in=["queued", "running"],
            deleted_at__isnull=True,
        ).first()
        if in_flight is not None:
            return Response(
                {
                    "error": "materialization already in flight",
                    "job_id": str(in_flight.id),
                    "status": in_flight.status,
                },
                status=status.HTTP_409_CONFLICT,
            )

        job = ProdocMaterializationJob.objects.create(
            workspace=project.workspace,
            project=project,
            template=template,
            start_date=req.validated_data["start_date"],
            created_by=request.user,
            updated_by=request.user,
        )
        prodoc_materialize_project.delay(str(job.id))
        return Response(
            {"job_id": str(job.id), "status": job.status},
            status=status.HTTP_202_ACCEPTED,
        )


class ProdocMaterializationJobDetailAPIEndpoint(
    ProdocFeatureFlagMixin, BaseAPIView
):
    permission_classes = [ProdocProjectEntityPermission]
    use_read_replica = False

    def get(self, request, slug, project_id, job_id):
        job = get_object_or_404(
            ProdocMaterializationJob,
            pk=job_id,
            project_id=project_id,
            project__workspace__slug=slug,
            deleted_at__isnull=True,
        )
        return Response(
            ProdocMaterializationJobSerializer(job).data,
            status=status.HTTP_200_OK,
        )
