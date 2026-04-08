"""
Resolve a template task's `role_key` to concrete project members.

The template author writes `role_key="admin"` (or "member", "guest").
At materialization time we translate that into whichever Plane
`ProjectMember` rows currently hold that role on the target project and
return them as a list of users. Zero matches is **non-fatal** — the
team may simply not have staffed that role yet. We record a warning on
the job row and leave the materialized issue unassigned; ops can fill
it in later without breaking the run.

Plane's role ints (see `apps/api/plane/db/models/project.py` —
`ROLE_CHOICES`): Guest=5, Member=15, Admin=20. We map the template's
string keys to those ints here so template JSON stays human-readable
and the planner never has to know about Plane's role numbering.
"""

from plane.db.models import ProjectMember

# String key -> Plane role int. Unknown keys resolve to empty list, not
# an error, so a template can safely reference a role the workspace
# hasn't defined yet (e.g. during a staged rollout).
_ROLE_KEY_TO_INT = {
    "admin": 20,
    "member": 15,
    "guest": 5,
}


def resolve_assignees(project, role_key, job=None):
    """Return a list of Users holding `role_key` on `project`.

    Non-fatal on zero — appends a note to `job.error_log` (if supplied)
    so the ops team can see which tasks landed unassigned without
    failing the whole materialization. The real
    `ProdocMaterializationJob` row (commit 6) stores `error_log` as a
    TextField; for commit 5 the engine's `_NullJob` stand-in exposes
    the same attribute.
    """
    role_int = _ROLE_KEY_TO_INT.get(role_key)
    if role_int is None:
        if job is not None:
            job.error_log += (
                f"role_key={role_key!r} not mapped; leaving tasks unassigned\n"
            )
        return []
    members = list(
        ProjectMember.objects.filter(
            project=project,
            role=role_int,
            is_active=True,
            deleted_at__isnull=True,
        ).select_related("member")
    )
    users = [m.member for m in members if m.member is not None]
    if not users and job is not None:
        job.error_log += (
            f"role_key={role_key!r} has no active members on project "
            f"{project.id}; leaving tasks unassigned\n"
        )
    return users
