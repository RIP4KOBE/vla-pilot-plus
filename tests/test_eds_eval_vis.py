import sys
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _DummyAdapter:
    def __init__(self):
        self.image = np.zeros((8, 8, 3), dtype=np.uint8)
        self.image[..., 1] = 64

    def get_vlm_image(self):
        return self.image.copy()


def _dummy_image(value):
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    image[..., 0] = value
    return image


def test_save_image_creates_parent_dirs(tmp_path):
    from utils.eds_eval_vis import save_image

    path = tmp_path / "qualitative" / "episode_000" / "frame.png"

    save_image(path, _dummy_image(127))

    assert path.exists()
    saved = imageio.imread(path)
    assert saved.shape == (8, 8, 3)
    assert saved[0, 0, 0] == 127


def test_save_eds_qualitative_artifacts_saves_expected_files(monkeypatch, tmp_path):
    import utils.eds_eval_vis as vis

    draw_calls = []

    def fake_draw_action_trajectory_on_vlm_image(**kwargs):
        action_chunk = vis._to_action_candidates(kwargs["action_chunk"])
        draw_calls.append(action_chunk.clone())
        return _dummy_image(10 + len(draw_calls))

    def fake_draw_keypoints_on_image(*, adapter, image, keypoints, mask_ids):
        assert keypoints.shape == (2, 3)
        assert mask_ids.tolist() == [3, 7]
        out = image.copy()
        out[..., 2] = 200
        return out

    monkeypatch.setattr(
        vis,
        "draw_action_trajectory_on_vlm_image",
        fake_draw_action_trajectory_on_vlm_image,
    )
    monkeypatch.setattr(vis, "draw_keypoints_on_image", fake_draw_keypoints_on_image)

    initial_actions = torch.zeros(3, 4, 7)
    initial_actions[:, :, 0] = torch.tensor([1.0, 2.0, 3.0])[:, None]
    final_actions = torch.zeros(3, 4, 7)
    final_actions[:, :, 0] = torch.tensor([10.0, 20.0, 30.0])[:, None]
    iter0_actions = torch.zeros(3, 4, 7)
    iter0_actions[:, :, 0] = torch.tensor([100.0, 200.0, 300.0])[:, None]
    iter1_actions = torch.zeros(3, 4, 7)
    iter1_actions[:, :, 0] = torch.tensor([400.0, 500.0, 600.0])[:, None]

    saved = vis.save_eds_qualitative_artifacts(
        output_dir=tmp_path / "qualitative",
        adapter=_DummyAdapter(),
        keypoints=np.ones((2, 3), dtype=np.float32),
        mask_ids=np.array([3, 7], dtype=np.int64),
        artifacts={
            "initial_actions": initial_actions,
            "final_actions": final_actions,
            "selected_idx": 1,
            "per_iter": [
                {
                    "iter_idx": 0,
                    "actions": iter0_actions,
                    "scores": torch.tensor([3.0, 1.0, 2.0]),
                },
                {
                    "iter_idx": 1,
                    "actions": iter1_actions,
                    "scores": torch.tensor([2.0, 1.0, 3.0]),
                },
            ],
        },
        episode=2,
        global_step=37,
        max_iters=1,
    )

    output_root = tmp_path / "qualitative" / "episode_002" / "chunk_000037"
    expected = {
        "keypoints_projected.png",
        "keypoints_selected_eef_overlay.png",
        "population_overlay_iter_last.png",
        "initial_best_vs_final_selected.png",
        "best_trajectory_overlay_iter_000.png",
        "population_cloud_iter_000.png",
    }

    assert {Path(path).name for path in saved} == expected
    assert {path.name for path in output_root.glob("*.png")} == expected
    assert not (output_root / "best_trajectory_overlay_iter_001.png").exists()
    assert not (output_root / "population_cloud_iter_001.png").exists()

    torch.testing.assert_close(draw_calls[0][:, 0, 0], torch.tensor([20.0]))
    torch.testing.assert_close(draw_calls[1][:, 0, 0], torch.tensor([10.0, 20.0, 30.0]))
    torch.testing.assert_close(draw_calls[2][:, 0, 0], torch.tensor([1.0]))
    torch.testing.assert_close(draw_calls[3][:, 0, 0], torch.tensor([20.0]))
    torch.testing.assert_close(draw_calls[4][:, 0, 0], torch.tensor([200.0]))
    torch.testing.assert_close(draw_calls[5][:, 0, 0], torch.tensor([100.0, 200.0, 300.0]))


def test_save_eds_qualitative_artifacts_falls_back_when_keypoint_draw_fails(
    monkeypatch,
    tmp_path,
):
    import utils.eds_eval_vis as vis

    def fake_draw_keypoints_on_image(**kwargs):
        raise RuntimeError("projection unavailable")

    monkeypatch.setattr(vis, "draw_keypoints_on_image", fake_draw_keypoints_on_image)

    saved = vis.save_eds_qualitative_artifacts(
        output_dir=tmp_path,
        adapter=_DummyAdapter(),
        keypoints=np.ones((1, 3), dtype=np.float32),
        mask_ids=None,
        artifacts={},
        episode=0,
        global_step=0,
    )

    path = tmp_path / "episode_000" / "chunk_000000" / "keypoints_projected.png"
    assert saved == [str(path)]
    assert path.exists()
    image = imageio.imread(path)
    assert image[0, 0, 1] == 64
