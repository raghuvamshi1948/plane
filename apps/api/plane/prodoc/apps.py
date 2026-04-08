from django.apps import AppConfig


class ProdocConfig(AppConfig):
    name = "plane.prodoc"
    verbose_name = "Prodoc Extensions"

    def ready(self):
        # Import signal handlers so they register before any view code runs.
        from plane.prodoc.signals import cascade  # noqa: F401
        from plane.prodoc.signals import dependency  # noqa: F401
