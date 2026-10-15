"""A stale cached target is corrected only when task and keypoint agree."""

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from c0_stage_identity_probe import corrected_stage_descriptions, content_for_f
from c0_stage_offline_diagnostic import content_for


def test_identity_probe_changes_only_stage_target_mentions():
    old = content_for(117)
    new = content_for_f(117)
    assert new[1:] == old[1:]
    before = old[0]["text"]
    after = new[0]["text"]
    assert before.count("alphabet soup can") == 4
    assert after == before.replace("alphabet soup can", "orange juice")


def test_identity_probe_preserves_matching_first_task():
    assert content_for_f(0) == content_for(0)


def test_identity_probe_fails_closed_on_task_keypoint_mismatch():
    original = "Stage 1: grasp alphabet soup can. Stage 2: move alphabet soup can."
    with pytest.raises(ValueError, match="disagree"):
        corrected_stage_descriptions(
            original, "pick up the orange juice and place it in the basket",
            {0: "ketchup_1_main"})
