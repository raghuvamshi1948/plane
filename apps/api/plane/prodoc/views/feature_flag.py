"""
ProdocFeatureFlag endpoint.

Mounted at /api/v1/prodoc/feature-flag/. Used by the web UI to decide
whether to render Prodoc components at all. Unlike every other Prodoc
endpoint, this one does NOT 404 when the flag is off — the frontend
needs a definitive yes/no to gate its UI, so we return `{enabled: bool}`
in both states. Existence of this endpoint is not sensitive since it
reveals only whether Prodoc is turned on for this instance.
"""

import os

from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView
from plane.license.utils.instance_value import get_configuration_value


class ProdocFeatureFlagAPIEndpoint(BaseAPIView):
    permission_classes = [AllowAny]

    def get(self, request):
        (PRODOC_FEATURES_ENABLED,) = get_configuration_value(
            [
                {
                    "key": "PRODOC_FEATURES_ENABLED",
                    "default": os.environ.get("PRODOC_FEATURES_ENABLED", "0"),
                }
            ]
        )
        return Response({"enabled": PRODOC_FEATURES_ENABLED == "1"})
