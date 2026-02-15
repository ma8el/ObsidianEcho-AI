"""Tests for logging with request IDs."""

import json
import logging

from fastapi.testclient import TestClient

from app.api.middleware.request_id import request_id_context
from app.core.logging import JSONFormatter, RequestIDFilter, TextFormatter
from app.main import create_app


class TestRequestIDFilter:
    """Tests for RequestIDFilter."""

    def test_filter_adds_request_id_when_in_context(self):
        """Test that filter adds request ID from context."""
        # Set a request ID in context
        request_id_context.set("req_test123")

        # Create a log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Apply filter
        filter_obj = RequestIDFilter()
        filter_obj.filter(record)

        # Check request_id was added
        assert hasattr(record, "request_id")
        assert record.request_id == "req_test123"

    def test_filter_adds_none_when_no_context(self):
        """Test that filter adds None when no request ID in context."""
        # Clear context
        request_id_context.set("")

        # Create a log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Apply filter
        filter_obj = RequestIDFilter()
        filter_obj.filter(record)

        # Check request_id is None
        assert hasattr(record, "request_id")
        assert record.request_id is None


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def test_format_includes_request_id(self):
        """Test that JSON formatter includes request ID."""
        # Create a log record with request_id
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.request_id = "req_test123"

        # Format the record
        formatter = JSONFormatter()
        output = formatter.format(record)

        # Parse JSON output
        log_data = json.loads(output)

        # Check request_id is included
        assert "request_id" in log_data
        assert log_data["request_id"] == "req_test123"
        assert log_data["message"] == "Test message"
        assert log_data["logger"] == "test.logger"

    def test_format_without_request_id(self):
        """Test that JSON formatter works without request ID."""
        # Create a log record without request_id
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.request_id = None

        # Format the record
        formatter = JSONFormatter()
        output = formatter.format(record)

        # Parse JSON output
        log_data = json.loads(output)

        # Check request_id is not included
        assert "request_id" not in log_data
        assert log_data["message"] == "Test message"


class TestTextFormatter:
    """Tests for TextFormatter."""

    def test_format_includes_request_id_in_message(self):
        """Test that text formatter includes request ID in message."""
        # Create a log record with request_id
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.request_id = "req_test123"

        # Format the record
        formatter = TextFormatter()
        output = formatter.format(record)

        # Check request_id is in the output
        assert "[req_test123]" in output
        assert "Test message" in output

    def test_format_without_request_id(self):
        """Test that text formatter works without request ID."""
        # Create a log record without request_id
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.request_id = None

        # Format the record
        formatter = TextFormatter()
        output = formatter.format(record)

        # Check output doesn't have brackets
        assert "[req_" not in output
        assert "Test message" in output


class TestRequestIDInLogs:
    """Integration tests for request IDs in logs."""

    def test_request_id_appears_in_endpoint_logs(self, caplog):
        """Test that request ID appears in logs during API request."""
        app = create_app()
        client = TestClient(app)

        with caplog.at_level(logging.INFO):
            response = client.get(
                "/health", headers={"X-API-Key": "oea_0123456789abcdef0123456789abcdef"}
            )

        # Get the request ID from response
        request_id = response.headers.get("X-Request-ID")
        assert request_id is not None

        # Check that at least one captured log record carries the request ID.
        # This avoids coupling the test to text/json formatter differences.
        assert any(getattr(record, "request_id", None) == request_id for record in caplog.records)
