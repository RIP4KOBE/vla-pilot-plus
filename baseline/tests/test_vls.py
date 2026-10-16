from pathlib import Path

import pytest

from baseline.io import read_json, write_json
from baseline.protocol import Protocol
from baseline.experiment import task_order
from baseline.vls import build_runtime_config, load_settings, summarize


ROOT = Path(__file__).resolve().parents[1] / "experiments/env_position20_20260910"


@pytest.fixture
def experiment():
    if not (ROOT / "v44_vls.json").is_file():
        pytest.skip("PR #2 historical VLS campaign artifacts were not committed: " + str(ROOT))
    cfg = load_settings(ROOT / "v44_vls.json")
    cfg["protocol"] = str(ROOT / "parent_protocol.json")
    cfg["task_selection"] = str(ROOT / "task_selection.json")
    cfg["runtime_template"] = str(ROOT / "vls_runtime_template.json")
    p = Protocol(cfg["protocol"])
    contexts = p.contexts(cfg["split"], cfg["seed"], task_order(cfg, p))
    return cfg, p, contexts


def test_vls_uses_same_twenty_cells_and_forty_probes(experiment):
    cfg, protocol, contexts = experiment
    assert len(contexts) == 40
    assert len({c["task_key"] for c in contexts}) == 20
    assert sum(c["perturbation_variant"] == "use_swap" for c in contexts) == 20
    assert {c["split"] for c in contexts} == {"fixed_development_probe"}
    assert all(str(c["init_state_id"]) not in protocol.tasks[c["task_key"]]["splits"]["demo_online_pool"]
               for c in contexts)


def test_runtime_does_not_inherit_live_destinations(experiment, tmp_path):
    cfg, _, contexts = experiment
    source = read_json(cfg["runtime_template"])
    actual = build_runtime_config(cfg, contexts[0], tmp_path)
    assert read_json(cfg["runtime_template"]) == source
    assert actual["mode_gate"]["enabled"] is False
    assert actual["mode_gate"]["auto_start_expansion_worker"] is False
    assert actual["policy"]["pi05"]["pretrained_path"] == cfg["checkpoint"]
    assert actual["main"]["cached_functions_dir"] is None
    assert actual["main"]["output_dir"] == str(tmp_path)
    assert actual["main"]["sample_batch_size"] == 40
    assert actual["backend"]["libero"]["auto_apply_perturbations"] is False
    assert actual["backend"]["libero"]["max_episode_steps"] == 720
    assert actual["backend"]["libero"]["num_steps_wait"] == 5
    for key, value in actual["mode_gate"].items():
        if key.endswith("_root"):
            assert Path(value).is_relative_to(tmp_path)
    for key in ("gemini", "gemini_grounding"):
        assert actual["perception"][key]["model"] == "gemini-3-flash-preview"
        assert "thinking_level" not in actual["perception"][key]
    assert Path(actual["perception"]["gemini"]["call_ledger_path"]).is_relative_to(tmp_path)
    assert actual["perception"]["vlm_agent"]["model"] == "gpt-5.1"
    assert actual["perception"]["vlm_agent"]["max_completion_tokens"] == 2000
    assert "references/vls/vlm_query" in actual["perception"]["vlm_agent"]["query_template_dir"]
    assert actual["perception"]["keypoint_detector"]["device"] == "cuda:0"


def test_each_context_changes_reset_and_policy_seeds(experiment, tmp_path):
    cfg, _, contexts = experiment
    for context in contexts:
        actual = build_runtime_config(cfg, context, tmp_path)
        assert actual["main"]["env_seed"] == actual["main"]["policy_seed"] == context["seed"]
        assert actual["main"]["init_state_id"] == context["init_state_id"]
        assert actual["backend"]["libero"]["suite_name"] == context["runtime_suite"]
        assert actual["backend"]["libero"]["task_ids_filter"] == [context["task_index"]]


@pytest.mark.parametrize("changes", [
    {"protected_gpu_indices": []}, {"device": "cuda:6"}, {"split": "policy_final_sealed"},
    {"stage_model": "gemini-robotics-er-2-preview"}, {"method": "clare"},
    {"stage_model": "gpt-6-astra"}, {"reward_model": "gpt-4o"}, {"provider": "codex_account"},
])
def test_refuses_protected_gpu_final_seal_and_provider_substitution(experiment, tmp_path, changes):
    cfg, _, _ = experiment
    write_json(tmp_path / "bad.json", {**cfg, **changes})
    with pytest.raises(ValueError):
        load_settings(tmp_path / "bad.json")


def test_summary_is_paired_and_invalid_episodes_are_not_failures(experiment):
    cfg, protocol, contexts = experiment
    reference = {"base": {"checkpoint": cfg["checkpoint"]}}
    paired = [{"context": c, "success": False} for c in contexts]
    row = {"context": contexts[0], "success": True, "valid": True, "steps": 123,
           "interventions": 12, "stage_queries": 2, "seconds": 10}
    summary = summarize([row], cfg, protocol, reference, paired, 40)
    assert summary["episodes"] == 1 and summary["successes"] == 1
    assert summary["partial_development_check"] is True
    assert summary["paired_outcomes"] == {"v44_0_vls_1": 1}
    with pytest.raises(ValueError, match="aborted/invalid"):
        summarize([{**row, "valid": False}], cfg, protocol, reference, paired, 40)
    with pytest.raises(ValueError, match="ordered prefix"):
        summarize([row, row], cfg, protocol, reference, paired, 40)
    empty = summarize([], cfg, protocol, reference, paired, 40)
    assert empty["micro_success"] is None and empty["episodes"] == 0
