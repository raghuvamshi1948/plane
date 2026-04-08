from django.urls import path

from plane.prodoc.views.dependency import IssueRelationDeleteAPIEndpoint
from plane.prodoc.views.holiday import (
    HolidayCalendarDetailAPIEndpoint,
    HolidayCalendarListCreateAPIEndpoint,
)
from plane.prodoc.views.materialize import (
    ProdocMaterializationJobDetailAPIEndpoint,
    ProdocMaterializeAPIEndpoint,
)
from plane.prodoc.views.project_settings import ProdocProjectSettingsAPIEndpoint
from plane.prodoc.views.reference import (
    ProdocMigrationRequirementDetailAPIEndpoint,
    ProdocMigrationRequirementListCreateAPIEndpoint,
    ProdocThirdPartyToolDetailAPIEndpoint,
    ProdocThirdPartyToolListCreateAPIEndpoint,
)
from plane.prodoc.views.site import (
    ProdocSiteDetailAPIEndpoint,
    ProdocSiteListCreateAPIEndpoint,
)
from plane.prodoc.views.wave import (
    ProdocWaveDetailAPIEndpoint,
    ProdocWaveListCreateAPIEndpoint,
    ProdocWaveSiteAttachAPIEndpoint,
    ProdocWaveSiteDetachAPIEndpoint,
)
from plane.prodoc.views.template import (
    ProdocTemplateDetailAPIEndpoint,
    ProdocTemplateListCreateAPIEndpoint,
    ProdocTemplateSectionDetailAPIEndpoint,
    ProdocTemplateSectionListCreateAPIEndpoint,
    ProdocTemplateTaskDependencyDetailAPIEndpoint,
    ProdocTemplateTaskDependencyListCreateAPIEndpoint,
    ProdocTemplateTaskDetailAPIEndpoint,
    ProdocTemplateTaskListCreateAPIEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/"
        "work-items/<uuid:issue_id>/relations/<uuid:relation_id>/",
        IssueRelationDeleteAPIEndpoint.as_view(http_method_names=["delete", "options"]),
        name="prodoc-work-item-relation-detail",
    ),
    path(
        "workspaces/<str:slug>/holiday-calendars/",
        HolidayCalendarListCreateAPIEndpoint.as_view(
            http_method_names=["get", "post", "options"]
        ),
        name="prodoc-holiday-calendar-list",
    ),
    path(
        "workspaces/<str:slug>/holiday-calendars/<uuid:pk>/",
        HolidayCalendarDetailAPIEndpoint.as_view(
            http_method_names=["get", "patch", "delete", "options"]
        ),
        name="prodoc-holiday-calendar-detail",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/settings/",
        ProdocProjectSettingsAPIEndpoint.as_view(
            http_method_names=["get", "patch", "options"]
        ),
        name="prodoc-project-settings",
    ),
    # ----- Templates -----
    path(
        "workspaces/<str:slug>/templates/",
        ProdocTemplateListCreateAPIEndpoint.as_view(
            http_method_names=["get", "post", "options"]
        ),
        name="prodoc-template-list",
    ),
    path(
        "workspaces/<str:slug>/templates/<uuid:template_id>/",
        ProdocTemplateDetailAPIEndpoint.as_view(
            http_method_names=["get", "patch", "delete", "options"]
        ),
        name="prodoc-template-detail",
    ),
    path(
        "workspaces/<str:slug>/templates/<uuid:template_id>/sections/",
        ProdocTemplateSectionListCreateAPIEndpoint.as_view(
            http_method_names=["get", "post", "options"]
        ),
        name="prodoc-template-section-list",
    ),
    path(
        "workspaces/<str:slug>/templates/<uuid:template_id>/sections/<uuid:section_id>/",
        ProdocTemplateSectionDetailAPIEndpoint.as_view(
            http_method_names=["get", "patch", "delete", "options"]
        ),
        name="prodoc-template-section-detail",
    ),
    path(
        "workspaces/<str:slug>/templates/<uuid:template_id>/tasks/",
        ProdocTemplateTaskListCreateAPIEndpoint.as_view(
            http_method_names=["get", "post", "options"]
        ),
        name="prodoc-template-task-list",
    ),
    path(
        "workspaces/<str:slug>/templates/<uuid:template_id>/tasks/<uuid:task_id>/",
        ProdocTemplateTaskDetailAPIEndpoint.as_view(
            http_method_names=["get", "patch", "delete", "options"]
        ),
        name="prodoc-template-task-detail",
    ),
    path(
        "workspaces/<str:slug>/templates/<uuid:template_id>/dependencies/",
        ProdocTemplateTaskDependencyListCreateAPIEndpoint.as_view(
            http_method_names=["get", "post", "options"]
        ),
        name="prodoc-template-dependency-list",
    ),
    path(
        "workspaces/<str:slug>/templates/<uuid:template_id>/dependencies/<uuid:dependency_id>/",
        ProdocTemplateTaskDependencyDetailAPIEndpoint.as_view(
            http_method_names=["delete", "options"]
        ),
        name="prodoc-template-dependency-detail",
    ),
    # ----- Reference data -----
    path(
        "workspaces/<str:slug>/migration-requirements/",
        ProdocMigrationRequirementListCreateAPIEndpoint.as_view(
            http_method_names=["get", "post", "options"]
        ),
        name="prodoc-migration-requirement-list",
    ),
    path(
        "workspaces/<str:slug>/migration-requirements/<uuid:pk>/",
        ProdocMigrationRequirementDetailAPIEndpoint.as_view(
            http_method_names=["get", "patch", "delete", "options"]
        ),
        name="prodoc-migration-requirement-detail",
    ),
    path(
        "workspaces/<str:slug>/third-party-tools/",
        ProdocThirdPartyToolListCreateAPIEndpoint.as_view(
            http_method_names=["get", "post", "options"]
        ),
        name="prodoc-third-party-tool-list",
    ),
    path(
        "workspaces/<str:slug>/third-party-tools/<uuid:pk>/",
        ProdocThirdPartyToolDetailAPIEndpoint.as_view(
            http_method_names=["get", "patch", "delete", "options"]
        ),
        name="prodoc-third-party-tool-detail",
    ),
    # ----- Sites -----
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/sites/",
        ProdocSiteListCreateAPIEndpoint.as_view(
            http_method_names=["get", "post", "options"]
        ),
        name="prodoc-site-list",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/sites/<uuid:site_id>/",
        ProdocSiteDetailAPIEndpoint.as_view(
            http_method_names=["get", "patch", "delete", "options"]
        ),
        name="prodoc-site-detail",
    ),
    # ----- Waves -----
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/waves/",
        ProdocWaveListCreateAPIEndpoint.as_view(
            http_method_names=["get", "post", "options"]
        ),
        name="prodoc-wave-list",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/waves/<uuid:wave_id>/",
        ProdocWaveDetailAPIEndpoint.as_view(
            http_method_names=["get", "patch", "delete", "options"]
        ),
        name="prodoc-wave-detail",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/waves/<uuid:wave_id>/sites/",
        ProdocWaveSiteAttachAPIEndpoint.as_view(
            http_method_names=["post", "options"]
        ),
        name="prodoc-wave-site-attach",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/waves/<uuid:wave_id>/sites/<uuid:site_id>/",
        ProdocWaveSiteDetachAPIEndpoint.as_view(
            http_method_names=["delete", "options"]
        ),
        name="prodoc-wave-site-detach",
    ),
    # ----- Materialize + jobs -----
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/materialize/",
        ProdocMaterializeAPIEndpoint.as_view(
            http_method_names=["post", "options"]
        ),
        name="prodoc-materialize",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/materialization-jobs/<uuid:job_id>/",
        ProdocMaterializationJobDetailAPIEndpoint.as_view(
            http_method_names=["get", "options"]
        ),
        name="prodoc-materialization-job-detail",
    ),
]
