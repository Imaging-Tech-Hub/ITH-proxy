"""
Custom DRF Renderers using orjson for better performance.
"""
from rest_framework.renderers import JSONRenderer
import orjson


class ORJSONRenderer(JSONRenderer):
    """
    Renderer that uses orjson for fast JSON serialization.
    """
    media_type = 'application/json'
    format = 'json'
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """
        Render `data` into JSON using orjson.
        """
        if data is None:
            return b''

        return orjson.dumps(
            data,
            option=orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY
        )
