"""CPU-only predicate reproducer for the engineering health lock-transfer concern.
No imports of project runtime, no approvals, no journal writes, no dispatch.
Evaluates the exact production guard AST, not the public vetoed entrypoint.
"""
import ast
import json
from pathlib import Path

source = Path("/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree/scripts/qd_ed_n36_healthcheck.py")
tree = ast.parse(source.read_text())
guard = next(node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr == "require"
             and any(isinstance(arg, ast.Constant) and arg.value == "healthcheck reservation changed; no replay"
                     for arg in node.args))
expression = compile(ast.Expression(guard.args[0]), str(source), "eval")
resource_id = "n36_healthcheck_engineering_t00_c0_001479"
record = {"resource_id": resource_id, "event": "reserved"}
cases = {
    "unchanged": [record],
    "foreign_reserved_during_lock_transfer": [record, {"resource_id": "foreign", "event": "reserved"}],
    "foreign_completed_during_lock_transfer": [record, {"resource_id": "foreign", "event": "completed"}],
    "same_id_replay": [record, dict(record)],
}
results = {name: eval(expression, {"resources": resources, "resource_id": resource_id, "record": record})
           for name, resources in cases.items()}
assert results == {"unchanged": True, "foreign_reserved_during_lock_transfer": True,
                   "foreign_completed_during_lock_transfer": True, "same_id_replay": False}
print(json.dumps({"schema": "n36-review-predicate-reproducer-v1", "guard_line": guard.lineno,
                  "results": results,
                  "limit": "Proves the post-transfer guard ignores foreign resources. Static call tracing establishes no intervening engineering live_journals/validate_state recheck. Does not bypass the dispatch veto or demonstrate actual release acceptance."}, indent=2))
