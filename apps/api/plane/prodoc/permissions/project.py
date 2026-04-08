from plane.app.permissions import ProjectEntityPermission


class ProdocProjectEntityPermission(ProjectEntityPermission):
    """
    Identical to upstream ProjectEntityPermission today. Exists as a
    Prodoc-side seam so future extensions can tighten or relax permissions
    without monkey-patching upstream classes.
    """

    pass
