from types import SimpleNamespace

import pytest

from vlm_query.vlm_agent import (
    call_openai_with_network_recovery,
    is_retryable_openai_network_error,
)


def test_openai_stream_restarts_without_returning_partial_output():
    attempts = []
    sleeps = []

    def request_once():
        attempt = len(attempts) + 1
        attempts.append(attempt)
        output = []
        output.append("partial" if attempt == 1 else "complete")
        if attempt == 1:
            raise TimeoutError("TLS handshake operation timed out")
        return "".join(output)

    output = call_openai_with_network_recovery(
        request_once,
        recovery_label="test stream",
        sleep_fn=sleeps.append,
    )

    assert output == "complete"
    assert attempts == [1, 2]
    assert sleeps == [10]


@pytest.mark.parametrize("status_code", [429, 500, 502, 503])
def test_openai_retry_classifier_accepts_transient_statuses(status_code):
    error = RuntimeError("provider failure")
    error.status_code = status_code
    assert is_retryable_openai_network_error(error)


def test_openai_retry_classifier_checks_nested_tls_cause():
    try:
        try:
            raise TimeoutError("TLS handshake operation timed out")
        except TimeoutError as cause:
            raise RuntimeError("OpenAI request failed") from cause
    except RuntimeError as error:
        assert is_retryable_openai_network_error(error)


def test_openai_retry_classifier_rejects_nontransient_errors():
    auth_error = RuntimeError("invalid API key")
    auth_error.response = SimpleNamespace(status_code=401)
    assert not is_retryable_openai_network_error(auth_error)

    with pytest.raises(ValueError, match="invalid response schema"):
        call_openai_with_network_recovery(
            lambda: (_ for _ in ()).throw(ValueError("invalid response schema")),
            recovery_label="test schema",
            sleep_fn=lambda _delay: pytest.fail("must not retry schema failures"),
        )
