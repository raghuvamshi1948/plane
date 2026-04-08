from django.urls import path

from plane.prodoc.views.dependency import IssueRelationDeleteAPIEndpoint
from plane.prodoc.views.holiday import (
    HolidayCalendarDetailAPIEndpoint,
    HolidayCalendarListCreateAPIEndpoint,
)
from plane.prodoc.views.project_settings import ProdocProjectSettingsAPIEndpoint

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
]
