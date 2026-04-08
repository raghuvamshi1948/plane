import os

from rest_framework.exceptions import NotFound

from plane.license.utils.instance_value import get_configuration_value


class ProdocFeatureFlagMixin:
    """
    Returns 404 (not 403) if PRODOC_FEATURES_ENABLED is not "1", so the
    existence of the endpoint isn't leaked to unauthorized callers.
    Per CLAUDE.md §8.

    Mirrors the canonical flag-check pattern used elsewhere in the
    upstream codebase, e.g.
    apps/api/plane/authentication/adapter/base.py:135 — get_configuration_value
    returns a tuple aligned with the input keys, and values are strings.
    """

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        (PRODOC_FEATURES_ENABLED,) = get_configuration_value(
            [
                {
                    "key": "PRODOC_FEATURES_ENABLED",
                    "default": os.environ.get("PRODOC_FEATURES_ENABLED", "0"),
                }
            ]
        )
        if PRODOC_FEATURES_ENABLED != "1":
            raise NotFound("Not found")
