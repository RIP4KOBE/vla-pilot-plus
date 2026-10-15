#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = WORKTREE_ROOT / "outputs" / "rdt_eds_mechanism_pretest"


def _hydra_optional(value: str | None) -> str:
    return "null" if value is None else str(value)


def build_pretest_command(
    *,
    reward_mode: str,
    output_root: Path,
    initial_sampling_mode: str = "iid",
    initial_diversity_scale: float = 1.0,
    initial_diversity_start_ratio: str | None = None,
) -> list[str]:
    return [
        "python",
        "main.py",
        "policy.type=rdt",
        "backend=libero",
        "backend.libero.suite_name=libero_object",
        "backend.libero.task_ids_filter=[1]",
        "backend.libero.max_episode_steps=240",
        "main.episode_num=1",
        "main.use_vlm_stage_recognition=true",
        "perception.gemini_grounding.enabled=true",
        "main.render=false",
        "main.visualize_trajectory=false",
        "main.debug_draw_trajectory=false",
        "main.use_guidance=true",
        "main.guidance_type=eds",
        "main.eds_config.population_size=16",
        "main.eds_config.cem_iters=10",
        "main.eds_config.use_cem=false",
        f"main.eds_config.initial_sampling_mode={initial_sampling_mode}",
        f"main.eds_config.initial_diversity_scale={initial_diversity_scale}",
        "main.eds_config.initial_diversity_start_ratio="
        f"{_hydra_optional(initial_diversity_start_ratio)}",
        "main.eds_eval.enabled=true",
        "main.eds_eval.write_metrics=true",
        "main.eds_eval.save_qualitative=false",
        f"main.eds_eval.reward_mode={reward_mode}",
        "main.eds_mechanism_pretest.enabled=true",
        "main.eds_mechanism_pretest.first_chunk_only=true",
        "main.eds_mechanism_pretest.save_single_step=true",
        "main.eds_mechanism_pretest.save_full_process=true",
        "main.eds_mechanism_pretest.save_tensors=true",
        "main.eds_mechanism_pretest.plot_3d=true",
        f"main.eds_mechanism_pretest.output_dir={output_root}",
        f"hydra.run.dir={output_root / ('hydra_' + reward_mode)}",
    ]


def build_control_commands(
    *,
    output_root: Path,
    initial_sampling_mode: str = "iid",
    initial_diversity_scale: float = 1.0,
    initial_diversity_start_ratio: str | None = None,
) -> list[list[str]]:
    return [
        build_pretest_command(
            reward_mode="zero",
            output_root=output_root,
            initial_sampling_mode=initial_sampling_mode,
            initial_diversity_scale=initial_diversity_scale,
            initial_diversity_start_ratio=initial_diversity_start_ratio,
        ),
        build_pretest_command(
            reward_mode="inverted",
            output_root=output_root,
            initial_sampling_mode=initial_sampling_mode,
            initial_diversity_scale=initial_diversity_scale,
            initial_diversity_start_ratio=initial_diversity_start_ratio,
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the RDT+EDS qualitative mechanism pretest.")
    parser.add_argument("--reward-mode", default="normal", choices=["normal", "zero", "inverted"])
    parser.add_argument(
        "--controls",
        action="store_true",
        help="Run zero and inverted controls instead of the selected reward mode.",
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--initial-sampling-mode", default="iid")
    parser.add_argument("--initial-diversity-scale", type=float, default=1.0)
    parser.add_argument("--initial-diversity-start-ratio", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    commands = (
        build_control_commands(
            output_root=args.output_root,
            initial_sampling_mode=args.initial_sampling_mode,
            initial_diversity_scale=args.initial_diversity_scale,
            initial_diversity_start_ratio=args.initial_diversity_start_ratio,
        )
        if args.controls
        else [
            build_pretest_command(
                reward_mode=args.reward_mode,
                output_root=args.output_root,
                initial_sampling_mode=args.initial_sampling_mode,
                initial_diversity_scale=args.initial_diversity_scale,
                initial_diversity_start_ratio=args.initial_diversity_start_ratio,
            )
        ]
    )
    for cmd in commands:
        print(" ".join(str(part) for part in cmd))
        if not args.dry_run:
            subprocess.run(cmd, cwd=WORKTREE_ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
