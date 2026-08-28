#!/usr/bin/env python
"""Validate hgpu1 Gemini credentials/model access without exposing secrets."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import sys
import time

from dotenv import load_dotenv
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mode_gate.io_utils import atomic_write_json  # noqa: E402
from mode_gate.preflight import gemini_canary_source_fingerprint  # noqa: E402
from mode_gate.semantic_planner import GeminiSemanticPlanner  # noqa: E402
from mode_gate.tickets import (  # noqa: E402
    TICKET_PLANNER_MODEL,
    TicketCollectionPlanner,
)
from core.gemini_grounder import GeminiGrounder, GeminiStageRecognizer  # noqa: E402


DEFAULT_OUTPUT = Path(
    "/shared/hengyil6/vls/self_improve/preflight/gemini_canary/result.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    # Four sequential requests, each independently capped at 60 seconds.
    parser.add_argument("--max-latency-seconds", type=float, default=240.0)
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env", override=False)
    credential_present = bool(
        os.environ.get("MODE_GATE_GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    )
    started = time.monotonic()
    error = None
    interaction_exercised = False
    grounding_exercised = False
    stage_exercised = False
    ticket_exercised = False
    grounding_detection_count = None
    stage_result = None
    ticket_result = None
    try:
        planner = GeminiSemanticPlanner(cache_dir=args.output.parent / "cache")
        planner.preflight(exercise_interactions=True)
        interaction_exercised = True

        # Exercise both migrated legacy visual paths with a synthetic scene.  This
        # verifies request/schema compatibility without exporting a simulator frame.
        image = np.full((128, 128, 3), 245, dtype=np.uint8)
        image[30:98, 34:94] = np.array([210, 25, 25], dtype=np.uint8)
        visual_config = {"model": "gemini-robotics-er-2-preview"}
        detections = GeminiGrounder(visual_config).detect_objects(
            image, ["large red rectangle"]
        )
        grounding_detection_count = len(detections)
        grounding_exercised = True

        stage_result = list(
            GeminiStageRecognizer(visual_config).identify_stage_and_guidance(
                image,
                "inspect the large red rectangle",
                "1: locate the rectangle; 2: inspection complete",
                num_stages=2,
                trigger_reason="provider canary",
            )
        )
        stage_exercised = True

        collection, ticket_provenance = TicketCollectionPlanner().plan(
            task_instruction="slide open the top drawer and place the bowl in it",
            failure_mode="UNKNOWN",
            required_trajectory_pattern=(
                "pull the top drawer open by moving the gripper from the drawer "
                "handle outwards"
            ),
            semantic_failure_types=(),
        )
        ticket_result = {
            "model": ticket_provenance["model"],
            "prompt_version": ticket_provenance["prompt_version"],
            "coverage_axis_count": len(collection.coverage_axes),
            "must_demonstrate_count": len(collection.must_demonstrate),
            "must_avoid_count": len(collection.must_avoid),
        }
        ticket_exercised = True
    except Exception as exc:  # Persist a sanitized failure for the blocking preflight.
        error = f"{type(exc).__name__}: {exc}"
    elapsed = time.monotonic() - started
    passed = (
        error is None
        and interaction_exercised
        and grounding_exercised
        and stage_exercised
        and ticket_exercised
        and elapsed <= args.max_latency_seconds
    )
    value = {
        "schema_version": "hgpu1-gemini-canary-v3",
        "source_fingerprint": gemini_canary_source_fingerprint(REPO_ROOT),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "host": socket.gethostname(),
        "model": "gemini-robotics-er-2-preview",
        "latency_seconds": elapsed,
        "max_latency_seconds": args.max_latency_seconds,
        "credential_present": credential_present,
        "interaction_exercised": interaction_exercised,
        "grounding_exercised": grounding_exercised,
        "grounding_detection_count": grounding_detection_count,
        "stage_exercised": stage_exercised,
        "stage_result": stage_result,
        "ticket_model": TICKET_PLANNER_MODEL,
        "ticket_exercised": ticket_exercised,
        "ticket_result": ticket_result,
        "visual_input_kind": "synthetic",
        "passed": passed,
        "error": error,
    }
    atomic_write_json(args.output, value)
    print(json.dumps(value, indent=2, sort_keys=True))
    if not passed:
        raise RuntimeError(f"Gemini canary failed: {error or 'latency threshold'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
