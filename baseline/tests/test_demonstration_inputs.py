import copy
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from baseline.config import load_config
from baseline.demonstration_inputs import CONTRACT, MARKER, PolicyInputDataset, checked_training_batch, policy_image, policy_state
from baseline.io import digest, read_json, write_json


def fixture_source(tmp_path):
    raw_root = tmp_path / "raw"
    write_json(raw_root / "meta/info.json", {"total_frames": 2})
    states = np.array([[.1, .2, .3, 3., .02, .01, .04, -.04],
                       [.4, .5, .6, 2.9, .03, .02, .01, -.01]], dtype=np.float32)
    path = tmp_path / "state.npy"
    np.save(path, states)
    manifest = tmp_path / "manifest.json"
    write_json(manifest, {"contract": CONTRACT, "task_key": "task", "source_curation_sha256": "curation",
                         "raw_root": str(raw_root.resolve()), "height": 2, "width": 2,
                         "source_info_sha256": digest(raw_root / "meta/info.json"), "validation": {"passed": True},
                         "episodes": [{"episode_index": 9, "frames": 2, "states_path": str(path), "states_sha256": digest(path)}]})
    source = {"root": str(raw_root), "task_key": "task", "source_curation_sha256": "curation", "episodes": [9],
              "policy_input": {"contract": CONTRACT, "manifest": str(manifest), "sha256": digest(manifest)}}
    cfg = load_config(overrides={"demonstration_contract": CONTRACT, "observation_height": 2, "observation_width": 2})
    return source, cfg, states


def test_dataset_replaces_state_by_episode_frame_without_changing_action_alignment(tmp_path):
    source, cfg, states = fixture_source(tmp_path)
    # Intentionally reverse dataset access order; global index is not frame_index.
    pixels = torch.tensor([[10, 20], [30, 40]], dtype=torch.float32).expand(3, 2, 2) / 255
    raw = [{"episode_index": torch.tensor(9), "frame_index": torch.tensor(frame),
            "observation.state": torch.full((8,), -7.), "observation.images.image": pixels.clone(),
            "observation.images.image2": pixels.clone(), "action": torch.arange(350).reshape(50, 7).float(),
            "action_is_pad": torch.arange(50) > frame, "task": "same instruction"} for frame in (1, 0)]
    dataset = PolicyInputDataset(raw, source, cfg)
    for i, frame in enumerate((1, 0)):
        item = dataset[i]
        torch.testing.assert_close(item["observation.state"], torch.from_numpy(states[frame]))
        torch.testing.assert_close(item["observation.images.image"], pixels.flip(-1, -2))
        assert torch.equal(item["action"], raw[i]["action"])
        assert torch.equal(item["action_is_pad"], raw[i]["action_is_pad"])
        assert item["task"] == raw[i]["task"] and item[MARKER] == CONTRACT
        assert MARKER not in raw[i] and torch.all(raw[i]["observation.state"] == -7)
    with pytest.raises(ValueError, match="exactly once"):
        PolicyInputDataset([dataset[0], dataset[1]], source, cfg)[0]


def test_refuses_old_sources_modified_sidecars_and_unconverted_batches(tmp_path):
    source, cfg, _ = fixture_source(tmp_path)
    with pytest.raises(ValueError, match="lacks a verified"):
        PolicyInputDataset([{}, {}], {k: v for k, v in source.items() if k != "policy_input"}, cfg)
    with pytest.raises(ValueError, match="uncorrected"):
        from baseline.data import latent_batch
        latent_batch([{"input_contract": None}], "cpu", "v44")
    for marker in (None, "old", [CONTRACT, "old"]):
        with pytest.raises(ValueError, match="unconverted"):
            checked_training_batch({MARKER: marker}, cfg)
    assert checked_training_batch({MARKER: [CONTRACT], "task": ["a"]}, cfg) == {"task": ["a"]}
    (tmp_path / "state.npy").write_bytes(b"changed")
    with pytest.raises(ValueError, match="sidecar checksum"):
        PolicyInputDataset([{}, {}], source, cfg)


def test_image_area_resize_and_both_axis_orientation_have_known_pixel_result():
    # Four constant 2x2 blocks: area resize must preserve their values.
    image = torch.tensor([[10, 20], [30, 40]], dtype=torch.float32).repeat_interleave(2, 0).repeat_interleave(2, 1)
    result = policy_image(image.expand(3, 4, 4) / 255, 2, 2)
    expected = torch.tensor([[40, 30], [20, 10]], dtype=torch.float32).expand(3, 2, 2) / 255
    torch.testing.assert_close(result, expected, rtol=0, atol=0)


def test_state_uses_eef_and_separate_fingers_with_online_quaternion_convention():
    pytest.importorskip("lerobot.processor.env_processor")
    result = policy_state([[.1, .2, .3]], [[0., 0., 0., 1.]], [[.04, -.04]])
    torch.testing.assert_close(result, torch.tensor([[.1, .2, .3, 0., 0., 0., .04, -.04]]))


def test_full_export_sequences_match_hdf5_without_trusting_filename_order(tmp_path):
    h5py = pytest.importorskip("h5py")
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    from baseline.prepare_demonstrations import match_recordings
    raw = tmp_path / "snapshot/lerobot"
    (raw / "data/chunk-000").mkdir(parents=True)
    table_rows, accepted = [], {}
    for episode, name, offset in ((0, "z.hdf5", 2.), (1, "a.hdf5", 5.)):
        states = np.full((4, 8), offset, dtype=np.float32)
        actions = np.arange(21, dtype=np.float32).reshape(3, 7) + offset
        path = tmp_path / name
        with h5py.File(path, "w") as h:
            h.create_dataset("observation/state", data=states)
            h.create_dataset("action", data=actions)
            h.create_dataset("simulator_state", data=np.zeros((4, 30)))
            h.attrs.update(ticket_id="ticket", init_state_id="3", env_seed=0)
        accepted[str(path)] = {}
        for frame in range(3):
            table_rows.append({"episode_index": episode, "frame_index": frame,
                               "observation.state": states[frame].tolist(), "action": actions[frame].tolist()})
    write_json(raw.parent / "curation.json", {"curation_sha256": "curation", "accepted": dict(reversed(list(accepted.items())))})
    pq.write_table(pa.Table.from_pylist(list(reversed(table_rows))), raw / "data/chunk-000/file-000.parquet")
    source = {"root": str(raw), "source_curation_sha256": "curation", "source_ticket_id": "ticket",
              "init_state_ids": ["3"], "episodes": [0, 1]}
    result = match_recordings(source)
    assert [(r["episode_index"], Path(r["source_hdf5"]).name) for r in result] == [(0, "z.hdf5"), (1, "a.hdf5")]
    table_rows[0]["action"][0] += 1
    pq.write_table(pa.Table.from_pylist(table_rows), raw / "data/chunk-000/file-000.parquet")
    with pytest.raises(ValueError, match="exactly match"):
        match_recordings(source)


def test_corrected_run_refuses_checkpoint_trained_on_old_inputs(tmp_path):
    from baseline.artifacts import save_stage, load_stage
    runtime, protocol = SimpleNamespace(identity={"sha256": "v44"}), SimpleNamespace(digest="protocol")
    method = SimpleNamespace(stages=["a"], state=lambda: {"weights": torch.ones(2)}, restore=lambda _: None)
    cfg = load_config()
    old = save_stage(tmp_path, 0, method, runtime, protocol, cfg)
    with pytest.raises(ValueError, match="restart from v44"):
        load_stage(old, runtime, protocol, method, {**cfg, "demonstration_contract": CONTRACT})


@pytest.mark.parametrize("simulator_difference", [0., 1e-11, 1e-7, 1.])
def test_duplicate_sequences_preserve_episode_weight_only_if_converted_states_are_equivalent(tmp_path, simulator_difference):
    import h5py
    import pyarrow as pa
    import pyarrow.parquet as pq
    from baseline.prepare_demonstrations import match_recordings
    raw = tmp_path / "snapshot/lerobot"
    (raw / "data/chunk-000").mkdir(parents=True)
    accepted, rows = {}, []
    for episode in range(2):
        path = tmp_path / f"copy_{episode}.hdf5"
        with h5py.File(path, "w") as h:
            h.create_dataset("observation/state", data=np.zeros((3, 8)))
            h.create_dataset("action", data=np.ones((2, 7)))
            h.create_dataset("simulator_state", data=np.full((3, 30), simulator_difference * episode))
            h.attrs.update(ticket_id="ticket", init_state_id="3")
        accepted[str(path)] = {}
        rows += [{"episode_index": episode, "frame_index": frame, "observation.state": [0.] * 8, "action": [1.] * 7}
                 for frame in range(2)]
    write_json(raw.parent / "curation.json", {"curation_sha256": "curation", "accepted": accepted})
    pq.write_table(pa.Table.from_pylist(rows), raw / "data/chunk-000/file-000.parquet")
    source = {"root": str(raw), "source_curation_sha256": "curation", "source_ticket_id": "ticket", "init_state_ids": ["3"], "episodes": [0, 1]}
    if simulator_difference <= 1e-9:
        result = match_recordings(source)
        assert len(result) == 2 and {r["equivalent_sequence_copies"] for r in result} == {2}
        assert len({r["source_hdf5"] for r in result}) == 2
    else:
        with pytest.raises(ValueError, match="different simulator states"):
            match_recordings(source)
        result = match_recordings(source, state_reader=lambda path, frames: np.zeros((frames, 8), dtype=np.float32))
        assert len(result) == 2 and all(r["equivalent_policy_state_max_abs_error"] == 0 for r in result)
        def unequal_policy_states(path, frames):
            value = 0. if Path(path).name == "copy_0.hdf5" else .01
            return np.full((frames, 8), value, dtype=np.float32)
        with pytest.raises(ValueError, match="different v44 policy states"):
            match_recordings(source, state_reader=unequal_policy_states)


def test_first_stage_validation_does_not_finish_the_campaign_or_advance_training(tmp_path):
    from baseline.campaign import finished_job
    write_json(tmp_path / "probe/summary.json", {"episodes": 2, "micro_success": .5})
    state = {"methods": {"clare": {"tasks_completed": 1, "evaluated": False}}}
    finished_job(state, {"name": "probe", "owner": "clare", "phase": "evaluate", "stage_validation": True}, tmp_path, 20)
    item = state["methods"]["clare"]
    assert item["first_stage_validated"] and item["tasks_completed"] == 1 and not item["evaluated"]


def test_method_placement_cannot_launch_unselected_method_or_protected_gpu(tmp_path):
    from baseline.campaign import method_placement, validate_pool
    path = tmp_path / "gpus.json"
    write_json(path, {"method_gpu_indices": {"clare": 3, "mlr_ifa": 7}})
    assert method_placement(path, [3, 7], ("clare", "mlr_ifa"))["mlr_ifa"] == 7
    with pytest.raises(ValueError):
        method_placement(path, [3, 7])
    with pytest.raises(ValueError):
        validate_pool([3, 6], {"clare": load_config()})


@pytest.mark.parametrize("method", ["rl2_vla", "continual_vla_rl"])
def test_new_imitation_option_preserves_existing_rl_configuration_hashes(method):
    import hashlib
    import json
    from baseline.tests.test_campaign import EXPERIMENT, require_history
    require_history()
    original = read_json(EXPERIMENT / f"{method}.json")
    loaded = load_config(EXPERIMENT / f"{method}.json")
    assert "demonstration_contract" not in loaded
    canonical = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert canonical(loaded) == canonical(original)


def test_fresh_pair_campaign_starts_only_clare_mlr_from_v44(tmp_path, monkeypatch):
    from baseline import campaign
    from baseline.tests.test_campaign import frozen_config, EXPERIMENT
    experiment, prepared = tmp_path / "config", tmp_path / "prepared"
    for method in ("clare", "mlr_ifa"):
        cfg = frozen_config()
        cfg.update(method=method, output_root=str(tmp_path / "outputs"),
                   protocol=str(EXPERIMENT / "parent_protocol.json"), demonstration_contract=CONTRACT)
        write_json(experiment / f"{method}.json", cfg)
    write_json(prepared / "demonstrations_000.json", {"tasks": []})
    mapping = experiment / "gpus.json"
    write_json(mapping, {"method_gpu_indices": {"clare": 3, "mlr_ifa": 7}})
    monkeypatch.setattr(campaign.os, "nice", lambda _: None)
    monkeypatch.setattr(campaign.signal, "signal", lambda *a: None)
    monkeypatch.setattr(campaign.subprocess, "check_output", lambda *a, **k: "3, GPU-3, 50000\n7, GPU-7, 60000\n")
    created = []
    def popen(command, **kwargs):
        created.append((command, kwargs["env"]["CUDA_VISIBLE_DEVICES"]))
        return SimpleNamespace(pid=1000000 + len(created), poll=lambda: None)
    monkeypatch.setattr(campaign.subprocess, "Popen", popen)
    class EndCheck(Exception):
        pass
    monkeypatch.setattr(campaign.time, "sleep", lambda _: (_ for _ in ()).throw(EndCheck()))
    args = SimpleNamespace(experiment_dir=experiment, gpus=[3, 7], ticket_root=tmp_path / "tickets", collect_repeats=5,
                           resume=False, methods=["clare", "mlr_ifa"], no_reference=True, prepared_sources=prepared,
                           method_gpus=mapping, validate_first_stage=True)
    with pytest.raises(EndCheck):
        campaign.run(args)
    status = read_json(tmp_path / "outputs/queue/status.json")
    assert set(status["methods"]) == {"clare", "mlr_ifa"}
    assert {j["owner"] for j in status["jobs"]} == {"clare", "mlr_ifa"}
    assert {gpu for _, gpu in created} == {"GPU-3", "GPU-7"}
    assert all("--resume" not in command and "--artifact" not in command for command, _ in created)
