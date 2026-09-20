"""Retry transient VLS API failures without advancing the simulation or its RNG."""
from datetime import datetime, timedelta, timezone
from itertools import count
import socket
import ssl
import time

from .io import append_json, write_json

RETRY_POLICY = {"name": "vls-network-retry-v1", "max_attempts": None,
                "initial_delay_seconds": 2, "max_delay_seconds": 60}


def status_code(exc):
    for code in (getattr(exc, "status_code", None), getattr(exc, "code", None),
                 getattr(getattr(exc, "response", None), "status_code", None)):
        if isinstance(code, int) and not isinstance(code, bool):
            return code
    return None


def transient_error(exc):
    code = status_code(exc)
    if code is not None:
        return code in (408, 409, 425, 429) or 500 <= code < 600
    if isinstance(exc, (ConnectionError, TimeoutError, ssl.SSLError, socket.gaierror)):
        return True
    # Both SDKs use httpx; OpenAI wraps its transport failures separately.
    import httpx
    from openai import APIConnectionError
    return isinstance(exc, (httpx.TransportError, APIConnectionError))


def retry_provider_call(operation, record, *, attempts_path, status_path, activity_path, retry_errors=()):
    """Return one complete response; logical query budgets count outside this loop.

    Each attempt has its own audit record. No random jitter is used, so waiting
    for the network cannot consume the simulator/policy random-number streams.
    Authentication and invalid requests propagate. Callers may explicitly retry
    a particular response-format exception without classifying it as networking.
    """
    base = dict(record)
    started = time.monotonic()

    def publish(value):
        record.clear()
        record.update(value)
        write_json(status_path, value)
        write_json(activity_path, value)

    for attempt in count(1):
        attempt_started = time.monotonic()
        value = {**base, "attempt": attempt, "retry_policy": RETRY_POLICY,
                 "attempt_started_at": datetime.now(timezone.utc).isoformat(), "status": "requesting"}
        publish(value)
        try:
            result = operation(value)
        except Exception as exc:
            response_error = isinstance(exc, retry_errors)
            retry = response_error or transient_error(exc)
            value.update(status="retry_wait" if retry else "failed", error_type=type(exc).__name__,
                         status_code=status_code(exc), attempt_seconds=time.monotonic() - attempt_started,
                         elapsed_seconds=time.monotonic() - started)
            if retry:
                delay = min(2 ** min(attempt, 6), RETRY_POLICY["max_delay_seconds"])
                value.update(retry_reason="response_format" if response_error else "transient_transport_or_service",
                             retry_delay_seconds=delay,
                             next_retry_at=(datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat())
            append_json(attempts_path, value)
            publish(value)
            if not retry:
                raise
            print(f"VLS {value['model']} request rejected ({type(exc).__name__}); "
                  f"attempt {attempt}, retrying in {delay}s without an attempt limit", flush=True)
            time.sleep(delay)
        else:
            value.update(status="complete", attempt_seconds=time.monotonic() - attempt_started,
                         elapsed_seconds=time.monotonic() - started)
            append_json(attempts_path, value)
            publish(value)
            return result
