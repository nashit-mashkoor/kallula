import json
import logging

from observability.context import reset_request_id, set_request_id
from observability.logging import JsonFormatter


def test_json_formatter_includes_request_id():
    token = set_request_id("test-request-id")
    try:
        record = logging.LogRecord(
            "test.logger", logging.INFO, "", 0, "hello", (), None
        )
        payload = json.loads(JsonFormatter().format(record))
    finally:
        reset_request_id(token)

    assert payload["message"] == "hello"
    assert payload["logger"] == "test.logger"
    assert payload["request_id"] == "test-request-id"


def test_json_formatter_without_request_id():
    record = logging.LogRecord("test.logger", logging.INFO, "", 0, "hello", (), None)

    payload = json.loads(JsonFormatter().format(record))

    assert "request_id" not in payload
