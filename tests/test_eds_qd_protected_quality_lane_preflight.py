from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "eds_qd_protected_quality_lane_preflight.py"
)
SPEC = importlib.util.spec_from_file_location(
    "eds_qd_protected_quality_lane_preflight", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


def test_integrated_suite_passes_all_frozen_mechanism_gates():
    suite = preflight.run_scientific_suite()

    assert suite["passed"] is True
    assert len(suite["gates"]) == 10
    assert all(suite["gates"].values())
    candidate = suite["cases"]["candidate_expanding"]["metrics"]
    comparator = suite["cases"]["comparator_expanding"]["metrics"]
    assert candidate["qd_secondary_parent_activation_count"] > 0
    assert candidate["qd_secondary_invariant_violation_count"] == 0
    assert comparator["qd_secondary_parent_activation_count"] == 0
    assert (candidate["search_evaluation_count"], candidate["qd_evaluation_count"]) == (
        176,
        176,
    )
    assert candidate["score_call_count"] == 11


def test_payload_is_double_run_deterministic_finite_and_secret_free():
    payload = preflight.build_payload()

    assert payload["passed"] is True
    assert payload["double_run_byte_identical"] is True
    assert payload["scientific_payload_sha256"] == payload["independent_replay_sha256"]
    assert payload["credential_match_count"] == 0
    assert preflight.base.strict_secret_match_count(payload) == 0
    assert json.loads(preflight.base.canonical_bytes(payload))["passed"] is True


def test_frozen_hashes_and_owned_write_targets_are_exact():
    actual = {
        path: preflight.base.sha256_file(preflight.REPO_ROOT / path)
        for path in preflight.EXPECTED_HASHES
    }

    assert actual == preflight.EXPECTED_HASHES
    assert (
        preflight.base.sha256_file(preflight.BASE_HARNESS_PATH)
        == preflight.BASE_HARNESS_SHA256
    )
    assert preflight.CANONICAL_PATH.parent == preflight.ANALYSIS_ROOT
    assert preflight.REPLAY_PATH.parent == preflight.ANALYSIS_ROOT
    assert preflight.ANALYSIS_ROOT.parent == preflight.OWNED_ROOT
