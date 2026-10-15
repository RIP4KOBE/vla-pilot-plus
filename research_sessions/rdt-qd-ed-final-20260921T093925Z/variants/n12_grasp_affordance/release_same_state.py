#!/usr/bin/env python3
"""Convert a frozen pending diagnostic to one-use release after recorded approval."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import uuid


HERE = Path(__file__).resolve().parent
PENDING = HERE / "same-state-plan.pending.v3.json"
PENDING_SHA256 = "27641d9f71b8f3fccd922b42b47dca12df2fb4b8a41e5bf61d3a344a332758d2"
RELEASE = HERE / "same-state-plan.approved.v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: release_same_state.py APPROVAL_RECORD.json")
    if RELEASE.exists():
        raise SystemExit("one-use diagnostic release already exists")
    approval_path = Path(sys.argv[1]).resolve()
    approval = json.loads(approval_path.read_text())
    if approval.get("scope_approved") is not True or approval.get("pending_plan_sha256") != PENDING_SHA256:
        raise RuntimeError("explicit approval does not match frozen diagnostic scope")
    if not isinstance(approval.get("user_reply"), str) or not approval["user_reply"].strip():
        raise RuntimeError("approval record lacks actual user reply")
    if not isinstance(approval.get("received_at_utc"), str) or not approval["received_at_utc"].endswith("Z"):
        raise RuntimeError("approval record lacks UTC receipt time")
    if sha256(PENDING) != PENDING_SHA256:
        raise RuntimeError("pending scientific plan changed")
    plan = json.loads(PENDING.read_text())
    if plan["approved"] is not False or plan["attempt_id"] is not None or plan["output_dir"] is not None:
        raise RuntimeError("pending plan is not inactive")
    boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    attempt_id = f"rdt-qd-ed-final-20260921T093925Z__n12_same_state_t03_20260928__{uuid.uuid4().hex[:12]}"
    plan.update(
        approved=True,
        approval_record=str(approval_path),
        approval_record_sha256=sha256(approval_path),
        pending_plan_sha256=PENDING_SHA256,
        boot_id=boot_id,
        attempt_id=attempt_id,
        output_dir=str(HERE / attempt_id),
    )
    with RELEASE.open("x") as stream:
        json.dump(plan, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"release": str(RELEASE), "sha256": sha256(RELEASE),
                      "attempt_id": attempt_id, "gpu": plan["physical_gpu"],
                      "max_transitions": plan["max_diagnostic_transitions"]}))


if __name__ == "__main__":
    main()
