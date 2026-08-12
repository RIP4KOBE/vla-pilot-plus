from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "eds_qd_degenerate_fallback_preflight.py"
)
SPEC = importlib.util.spec_from_file_location(
    "eds_qd_degenerate_fallback_preflight",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


def test_integrated_scientific_suite_passes_every_frozen_gate():
    suite = preflight.run_scientific_suite()

    assert suite["passed"] is True
    assert suite["gates"]
    assert all(suite["gates"].values())
    zero = suite["cases"]["candidate_exact_zero"]["metrics"]
    legacy = suite["cases"]["legacy_qd_exact_zero"]["metrics"]
    near = suite["cases"]["candidate_near_equal"]["metrics"]
    assert (zero["search_evaluation_count"], zero["score_call_count"]) == (176, 11)
    assert zero["qd_evaluation_count"] == 0
    assert legacy["qd_evaluation_count"] == 176
    assert near["qd_degenerate_fallback_used"] is False


def test_full_payload_is_double_run_deterministic_and_secret_free():
    payload = preflight.build_payload()

    assert payload["passed"] is True
    assert payload["double_run_byte_identical"] is True
    assert (
        payload["scientific_payload_sha256"]
        == payload["independent_replay_sha256"]
    )
    assert payload["credential_match_count"] == 0
    assert preflight.strict_secret_match_count(payload) == 0
    assert json.loads(preflight.canonical_bytes(payload))["passed"] is True


def test_frozen_algorithm_hashes_and_write_targets_are_exact():
    actual = {
        path: preflight.sha256_file(preflight.REPO_ROOT / path)
        for path in preflight.EXPECTED_HASHES
    }

    assert actual == preflight.EXPECTED_HASHES
    assert preflight.CANONICAL_PATH.parent == preflight.ANALYSIS_ROOT
    assert preflight.REPLAY_PATH.parent == preflight.ANALYSIS_ROOT
    assert preflight.ANALYSIS_ROOT.parent == preflight.OWNED_ROOT
