"""
Custom DRF Parsers using orjson for better performance.
"""
from rest_framework.parsers import JSONParser
from rest_framework.exceptions import ParseError
import orjson


class ORJSONParser(JSONParser):
    """
    Parser that uses orjson for fast JSON deserialization.
    """
    media_type = 'application/json'

    def parse(self, stream, media_type=None, parser_context=None):
        """
        Parse the incoming bytestream as JSON using orjson.
        """
        parser_context = parser_context or {}
        encoding = parser_context.get('encoding', 'utf-8')

        try:
            data = stream.read()
            return orjson.loads(data)
        except orjson.JSONDecodeError as exc:
            raise ParseError(f'JSON parse error - {exc}')
