from django.urls import path

from plane.prodoc.views.dependency import IssueRelationDeleteAPIEndpoint

urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/"
        "work-items/<uuid:issue_id>/relations/<uuid:relation_id>/",
        IssueRelationDeleteAPIEndpoint.as_view(http_method_names=["delete", "options"]),
        name="prodoc-work-item-relation-detail",
    ),
]
