"""
data_connectors/telemetry.py -- request-level instrumentation for SEC
connector fetch_* functions.

Per the standing rule that a probe report must not overstate confidence:
H11's first real probe run against live SEC data completed without a
single failure, but the report couldn't say whether that reflected
genuinely healthy SEC access or just that nothing happened to fail. This
module exists to answer that question going forward -- every fetch_*
function that accepts an optional `telemetry` collector records exactly
what happened on the wire (endpoint, HTTP status, response size, timestamp,
retry count, any rate-limit headers SEC sends) independent of whether the
call ultimately succeeded.

Deliberately additive, not a behavior change: `telemetry` defaults to
None everywhere it's threaded through, in which case nothing is recorded
and every fetch_* function behaves byte-for-byte as it did before this
module existed -- same requests, same exceptions, same return values.

Retry logic does not exist anywhere in this project's connectors yet.
retry_count is always 0 for now; the field exists so a future retry
implementation has somewhere to report to without a second instrumentation
pass across every connector.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import requests

# SEC does not formally document rate-limit response headers (unlike, say,
# GitHub's X-RateLimit-*), so this list is opportunistic: capture these if
# present, record nothing if not, rather than assuming any of them exist.
_RATE_LIMIT_HEADER_NAMES = ("Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset")


@dataclass(frozen=True)
class RequestRecord:
    endpoint: str
    http_status: int | None
    response_size_bytes: int | None
    timestamp: str
    elapsed_seconds: float
    retry_count: int = 0
    rate_limit_headers: dict[str, str] = field(default_factory=dict)
    error: str | None = None  # populated when the request failed before any status code was available


class RequestTelemetryCollector:
    """
    Pass one of these into any fetch_* function's `telemetry` parameter to
    record what happened on the wire. A single collector is meant to be
    shared across every fetch_* call in one probe/backtest run, so
    `.summary()` reflects the whole run's SEC access health, not just one
    request.
    """

    def __init__(self) -> None:
        self.records: list[RequestRecord] = []

    def record(
        self,
        *,
        endpoint: str,
        http_status: int | None,
        response_size_bytes: int | None,
        elapsed_seconds: float,
        headers: Any = None,
        retry_count: int = 0,
        error: str | None = None,
    ) -> None:
        rate_limit_headers: dict[str, str] = {}
        if headers is not None:
            for name in _RATE_LIMIT_HEADER_NAMES:
                if name in headers:
                    rate_limit_headers[name] = str(headers[name])
        self.records.append(
            RequestRecord(
                endpoint=endpoint,
                http_status=http_status,
                response_size_bytes=response_size_bytes,
                timestamp=pd.Timestamp.utcnow().isoformat(),
                elapsed_seconds=elapsed_seconds,
                retry_count=retry_count,
                rate_limit_headers=rate_limit_headers,
                error=error,
            )
        )

    def summary(self) -> dict:
        """
        Aggregate view answering the actual question this module exists
        for: total requests, status-code distribution, failure count, and
        whether SEC sent any rate-limit signal at all during this run.
        """
        if not self.records:
            return {
                "total_requests": 0,
                "status_code_distribution": {},
                "failed_requests": 0,
                "any_rate_limit_headers_observed": False,
                "total_response_bytes": 0,
                "total_elapsed_seconds": 0.0,
            }
        status_counts: dict[str, int] = {}
        failed = 0
        any_rate_limit = False
        total_bytes = 0
        total_elapsed = 0.0
        for r in self.records:
            key = str(r.http_status) if r.http_status is not None else "no_response"
            status_counts[key] = status_counts.get(key, 0) + 1
            if r.error is not None or (r.http_status is not None and r.http_status >= 400):
                failed += 1
            if r.rate_limit_headers:
                any_rate_limit = True
            total_bytes += r.response_size_bytes or 0
            total_elapsed += r.elapsed_seconds
        return {
            "total_requests": len(self.records),
            "status_code_distribution": status_counts,
            "failed_requests": failed,
            "any_rate_limit_headers_observed": any_rate_limit,
            "total_response_bytes": total_bytes,
            "total_elapsed_seconds": round(total_elapsed, 3),
        }

    def to_records(self) -> list[dict]:
        return [
            {
                "endpoint": r.endpoint,
                "http_status": r.http_status,
                "response_size_bytes": r.response_size_bytes,
                "timestamp": r.timestamp,
                "elapsed_seconds": r.elapsed_seconds,
                "retry_count": r.retry_count,
                "rate_limit_headers": r.rate_limit_headers,
                "error": r.error,
            }
            for r in self.records
        ]


def instrumented_get(
    session: requests.Session,
    url: str,
    *,
    headers: dict[str, str],
    timeout: float,
    endpoint_label: str,
    telemetry: RequestTelemetryCollector | None = None,
) -> requests.Response:
    """
    Shared request wrapper for every connector's fetch_* function.
    Deliberately behavior-preserving: identical to calling
    `session.get(url, headers=headers, timeout=timeout)` followed by
    `resp.raise_for_status()` -- same exceptions propagate to the caller,
    same return value on success. The only addition is that if a
    `telemetry` collector is supplied, exactly one RequestRecord is
    recorded per call, with the real HTTP status code whenever a response
    was received at all (even a 4xx/5xx one, recorded BEFORE
    raise_for_status() raises on it -- not skipped just because the
    request ultimately failed).
    """
    start = time.monotonic()
    try:
        resp = session.get(url, headers=headers, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        elapsed = time.monotonic() - start
        if telemetry is not None:
            telemetry.record(
                endpoint=endpoint_label,
                http_status=None,
                response_size_bytes=None,
                elapsed_seconds=elapsed,
                error=str(exc),
            )
        raise

    elapsed = time.monotonic() - start
    if telemetry is not None:
        telemetry.record(
            endpoint=endpoint_label,
            http_status=resp.status_code,
            response_size_bytes=len(resp.content) if resp.content is not None else None,
            elapsed_seconds=elapsed,
            headers=resp.headers,
        )
    resp.raise_for_status()
    return resp
