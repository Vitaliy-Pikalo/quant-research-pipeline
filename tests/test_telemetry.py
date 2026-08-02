"""
tests/test_telemetry.py -- unit tests for data_connectors/telemetry.py,
fully synthetic, no network.

Uses a fake requests.Session-like object (FakeSession) so
instrumented_get()'s actual request/exception/recording logic gets
exercised without touching the real `requests` library or any network
call -- the same "test the real function against a fake transport" pattern
used in tests/test_h11_data_probe_e2e.py.
"""
from __future__ import annotations

import requests
import pytest

from data_connectors.telemetry import RequestTelemetryCollector, instrumented_get


class FakeResponse:
    def __init__(self, status_code=200, content=b"", headers=None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.exceptions.HTTPError(f"{self.status_code} error")
            err.response = self
            raise err


class FakeSession:
    def __init__(self, response=None, exception=None):
        self._response = response
        self._exception = exception
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "timeout": timeout})
        if self._exception is not None:
            raise self._exception
        return self._response


class TestInstrumentedGetBehaviorPreservation:
    """instrumented_get() must behave identically to a plain session.get()
    + raise_for_status() when telemetry=None -- these tests would pass
    even before telemetry.py existed, which is the point."""

    def test_returns_the_response_on_success(self):
        session = FakeSession(response=FakeResponse(status_code=200, content=b"hello"))
        resp = instrumented_get(session, "https://data.sec.gov/x", headers={}, timeout=30, endpoint_label="test")
        assert resp.status_code == 200
        assert resp.content == b"hello"

    def test_raises_on_http_error_status(self):
        session = FakeSession(response=FakeResponse(status_code=404, content=b""))
        with pytest.raises(requests.exceptions.HTTPError):
            instrumented_get(session, "https://data.sec.gov/x", headers={}, timeout=30, endpoint_label="test")

    def test_raises_on_connection_error(self):
        session = FakeSession(exception=requests.exceptions.ConnectionError("boom"))
        with pytest.raises(requests.exceptions.ConnectionError):
            instrumented_get(session, "https://data.sec.gov/x", headers={}, timeout=30, endpoint_label="test")

    def test_passes_through_headers_and_timeout_unchanged(self):
        session = FakeSession(response=FakeResponse(status_code=200))
        instrumented_get(
            session, "https://data.sec.gov/x", headers={"User-Agent": "me me@x.com"}, timeout=17, endpoint_label="test"
        )
        assert session.calls[0]["headers"] == {"User-Agent": "me me@x.com"}
        assert session.calls[0]["timeout"] == 17

    def test_none_telemetry_records_nothing_and_does_not_raise_on_its_own(self):
        session = FakeSession(response=FakeResponse(status_code=200))
        # no telemetry collector supplied at all -- must not error
        instrumented_get(session, "https://data.sec.gov/x", headers={}, timeout=30, endpoint_label="test")


class TestTelemetryRecordingOnSuccess:
    def test_records_status_and_size_on_success(self):
        telemetry = RequestTelemetryCollector()
        session = FakeSession(response=FakeResponse(status_code=200, content=b"0123456789"))
        instrumented_get(session, "https://data.sec.gov/x", headers={}, timeout=30, endpoint_label="submissions", telemetry=telemetry)

        assert len(telemetry.records) == 1
        r = telemetry.records[0]
        assert r.endpoint == "submissions"
        assert r.http_status == 200
        assert r.response_size_bytes == 10
        assert r.error is None
        assert r.elapsed_seconds >= 0

    def test_captures_rate_limit_headers_when_present(self):
        telemetry = RequestTelemetryCollector()
        session = FakeSession(response=FakeResponse(status_code=200, headers={"Retry-After": "5", "Unrelated-Header": "x"}))
        instrumented_get(session, "https://data.sec.gov/x", headers={}, timeout=30, endpoint_label="submissions", telemetry=telemetry)

        r = telemetry.records[0]
        assert r.rate_limit_headers == {"Retry-After": "5"}
        assert "Unrelated-Header" not in r.rate_limit_headers

    def test_no_rate_limit_headers_present_records_empty_dict(self):
        telemetry = RequestTelemetryCollector()
        session = FakeSession(response=FakeResponse(status_code=200, headers={}))
        instrumented_get(session, "https://data.sec.gov/x", headers={}, timeout=30, endpoint_label="submissions", telemetry=telemetry)
        assert telemetry.records[0].rate_limit_headers == {}


class TestTelemetryRecordingOnFailure:
    def test_records_http_error_status_before_raising(self):
        # THE key behavior this module exists for: a 4xx/5xx response is
        # still a "response" -- its real status code must be recorded, not
        # swallowed just because raise_for_status() subsequently raises.
        telemetry = RequestTelemetryCollector()
        session = FakeSession(response=FakeResponse(status_code=403, content=b"blocked"))
        with pytest.raises(requests.exceptions.HTTPError):
            instrumented_get(session, "https://data.sec.gov/x", headers={}, timeout=30, endpoint_label="submissions", telemetry=telemetry)

        assert len(telemetry.records) == 1
        r = telemetry.records[0]
        assert r.http_status == 403
        assert r.error is None  # the response WAS received -- this isn't a connection-level error

    def test_records_connection_error_with_no_status_code(self):
        telemetry = RequestTelemetryCollector()
        session = FakeSession(exception=requests.exceptions.ConnectionError("DNS failure"))
        with pytest.raises(requests.exceptions.ConnectionError):
            instrumented_get(session, "https://data.sec.gov/x", headers={}, timeout=30, endpoint_label="submissions", telemetry=telemetry)

        assert len(telemetry.records) == 1
        r = telemetry.records[0]
        assert r.http_status is None
        assert r.response_size_bytes is None
        assert "DNS failure" in r.error

    def test_retry_count_defaults_to_zero(self):
        # no retry logic exists anywhere yet -- this locks in that default
        # so a future retry implementation's absence is visible, not assumed
        telemetry = RequestTelemetryCollector()
        session = FakeSession(response=FakeResponse(status_code=200))
        instrumented_get(session, "https://data.sec.gov/x", headers={}, timeout=30, endpoint_label="submissions", telemetry=telemetry)
        assert telemetry.records[0].retry_count == 0


class TestSummary:
    def test_empty_collector_summary_is_well_formed(self):
        telemetry = RequestTelemetryCollector()
        summary = telemetry.summary()
        assert summary["total_requests"] == 0
        assert summary["failed_requests"] == 0
        assert summary["any_rate_limit_headers_observed"] is False

    def test_summary_counts_status_codes_and_failures(self):
        telemetry = RequestTelemetryCollector()
        for status in (200, 200, 404, 200):
            session = FakeSession(response=FakeResponse(status_code=status, content=b"x"))
            try:
                instrumented_get(session, "https://data.sec.gov/x", headers={}, timeout=30, endpoint_label="e", telemetry=telemetry)
            except requests.exceptions.HTTPError:
                pass
        summary = telemetry.summary()
        assert summary["total_requests"] == 4
        assert summary["status_code_distribution"] == {"200": 3, "404": 1}
        assert summary["failed_requests"] == 1

    def test_summary_flags_connection_errors_as_failures_with_no_response_bucket(self):
        telemetry = RequestTelemetryCollector()
        session = FakeSession(exception=requests.exceptions.Timeout("slow"))
        try:
            instrumented_get(session, "https://data.sec.gov/x", headers={}, timeout=30, endpoint_label="e", telemetry=telemetry)
        except requests.exceptions.Timeout:
            pass
        summary = telemetry.summary()
        assert summary["status_code_distribution"] == {"no_response": 1}
        assert summary["failed_requests"] == 1

    def test_summary_detects_rate_limit_signal_across_run(self):
        telemetry = RequestTelemetryCollector()
        session1 = FakeSession(response=FakeResponse(status_code=200, headers={}))
        session2 = FakeSession(response=FakeResponse(status_code=200, headers={"X-RateLimit-Remaining": "10"}))
        instrumented_get(session1, "u", headers={}, timeout=30, endpoint_label="e", telemetry=telemetry)
        instrumented_get(session2, "u", headers={}, timeout=30, endpoint_label="e", telemetry=telemetry)
        assert telemetry.summary()["any_rate_limit_headers_observed"] is True

    def test_to_records_round_trips_through_json_safely(self):
        import json

        telemetry = RequestTelemetryCollector()
        session = FakeSession(response=FakeResponse(status_code=200, content=b"abc"))
        instrumented_get(session, "https://data.sec.gov/x", headers={}, timeout=30, endpoint_label="e", telemetry=telemetry)
        json.dumps(telemetry.to_records(), default=str)  # must not raise
        assert telemetry.to_records()[0]["http_status"] == 200
