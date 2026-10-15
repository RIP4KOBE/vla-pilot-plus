#!/usr/bin/env python3
"""Preserve interrupted attempt1 and run a full fresh cohort after transport repair."""
import argparse
import json
import shutil

import c0_poe_fresh_retest as fresh
import c0_poe_online_retest as runner
from c0_poe_resilient_worker import POLICY
from c0_trace_replay import STUDY, atomic_json, digest

OUTPUT = fresh.ROOT / "outputs/c0_poe_fresh_attempt2"
TRANSPORT_MANIFEST = fresh.ROOT / "transport-manifest-attempt2.json"
original_command = fresh.command
original_prepare = fresh.prepare
original_audit = fresh.audit


def command():
    argv = original_command()
    assert argv[1] == "main.py"
    argv[1] = "scripts/c0_poe_resilient_worker.py"
    return argv


def prepare():
    proof = json.loads((fresh.ROOT / "transport-probe.json").read_text())
    if not proof["ok"]:
        raise RuntimeError("Transport probe has not passed")
    manifest = original_prepare()
    files = ["scripts/c0_poe_resilient_worker.py", "scripts/c0_poe_fresh_recovery.py"]
    transport = {"policy": POLICY, "model_request_payload_changed": False,
        "semantic_response_retry": False, "original_manifest_sha256": digest(fresh.MANIFEST),
        "source_sha256": {name: digest(STUDY / name) for name in files},
        "probe_sha256": digest(fresh.ROOT / "transport-probe.json"),
        "amendment_sha256": digest(fresh.ROOT / "transport-recovery-amendment.json")}
    if TRANSPORT_MANIFEST.exists() and json.loads(TRANSPORT_MANIFEST.read_text()) != transport:
        raise RuntimeError("Frozen transport manifest changed")
    atomic_json(TRANSPORT_MANIFEST, transport)
    for name in files:
        dest = fresh.ROOT / "frozen_source" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and digest(dest) != digest(STUDY / name):
            raise RuntimeError("Frozen transport source changed")
        if not dest.exists():
            shutil.copy2(STUDY / name, dest)
    return manifest


def audit():
    result = original_audit()
    transport = json.loads(TRANSPORT_MANIFEST.read_text())
    changed = [name for name, h in transport["source_sha256"].items() if digest(STUDY / name) != h]
    if changed:
        result["problems"].append("transport_source_changed")
    result["valid"] = not result["problems"]
    result["transport_policy"] = POLICY
    result["transport_source_unchanged"] = not changed
    atomic_json(OUTPUT / "audit.json", result)
    return result


def configure():
    fresh.OUTPUT = OUTPUT
    fresh.MANIFEST = fresh.ROOT / "manifest-attempt2.json"
    fresh.command = command
    fresh.prepare = prepare
    fresh.audit = audit
    fresh.configure_runner()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "audit", "progress"))
    args = parser.parse_args()
    configure()
    if args.action == "run":
        runner.run()
    else:
        print(json.dumps({"prepare": prepare, "audit": audit, "progress": runner.progress}[args.action](), indent=2))
