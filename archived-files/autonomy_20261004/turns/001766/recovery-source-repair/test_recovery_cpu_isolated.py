"""Extract only CPU fixture/test bodies; never import production modules."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import pytest
ROOT = Path("/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_r1_001617/implementation_worktree")
RECOVERY_CPU_SOURCE = ROOT / "scripts/qd_ed_n36_engineering_r1.py"
source = ROOT / "tests/test_n36_engineering_r1.py"
tree = ast.parse(source.read_text())
nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and
         (n.name in {"recovery_cpu", "recovery_multi_cpu"} or n.name.startswith(("test_recovery_cpu_", "test_recovery_multi_cpu_", "test_recovery_prospective_cpu_")))]
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), globals())
