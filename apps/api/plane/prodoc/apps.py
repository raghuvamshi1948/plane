from django.apps import AppConfig


class ProdocConfig(AppConfig):
    name = "plane.prodoc"
    verbose_name = "Prodoc Extensions"

    def ready(self):
        # Import signal handlers so post_save / post_delete on IssueRelation
        # are registered before any view code runs.
        from plane.prodoc.signals import dependency  # noqa: F401
