"""CPU-only deterministic repair artifact construction; no source placement or release."""
import json
import sys
from pathlib import Path

ROOT = Path("/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_r1_001617/implementation_worktree")
sys.path.insert(0, str(ROOT))
from scripts import qd_ed_n36_engineering_r1 as e
from scripts import qd_ed_n36_stop as stop


def write_once(path, value):
    path = Path(path)
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError("Existing artifact differs; never overwrite: " + str(path))
    else:
        path.write_bytes(data)
    return {"path": str(path), "sha256": e.w.sha(path)}


stop.check(need=60)
spec = e.specification()
policy = spec["runtime_binding"]
source = e.b.closure.source_record(ROOT, e.b.source_paths(ROOT))
source_ref = write_once(policy["source_record_path"], source)
runtime = e.read(spec["canonical_runtime"])
runtime["preparation"]["source"] = source["commit"]
runtime["preparation"]["source_record"] = source_ref
runtime_ref = write_once(policy["runtime_path"], runtime)
e.validate_runtime_binding({"source": source, "scientific_source": source, "runtime": runtime_ref})
print(json.dumps({"status": "PASS_DISABLED_BINDING_ONLY", "source": source["commit"], "runtime": runtime_ref}))
