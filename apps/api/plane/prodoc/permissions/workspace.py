from plane.app.permissions import WorkspaceEntityPermission


class ProdocWorkspaceEntityPermission(WorkspaceEntityPermission):
    """
    Identical to upstream WorkspaceEntityPermission today. Exists as a
    Prodoc-side seam so future extensions can tighten or relax permissions
    without monkey-patching upstream classes. Mirrors the
    `ProdocProjectEntityPermission` pattern from Extension 1.
    """

    pass
