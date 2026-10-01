"""Test-only exact legacy function bodies, with synthetic static contract globals.

Avoid original contract's import-time read of the real frozen N22 plan. No
production globals or legacy modules are modified; substantive validator bodies
and their source identity stay exactly the committed legacy source.
"""
import ast,copy,importlib.util,json,types
from pathlib import Path
import pytest,yaml
from scripts import qd_ed_final_runner as runner,qd_ed_n23_worker as worker,qd_ed_n27_contract as c,qd_ed_n27_recovery as recovery


def contract():
    return types.SimpleNamespace(COHORT=c.COHORT,ref=c.ref,sha=worker.sha,OBSERVABILITY=runner.ROOT/'experiments/iteration_023_actuator_clipped_quality/timeout-observability-addendum-v2.md',OBSERVABILITY_SHA=c.OBSERVABILITY_SHA)


def install_classifier(monkeypatch):
    path=runner.ROOT/'scripts/qd_ed_n23_v2_recovery.py';tree=ast.parse(path.read_text())
    tree.body=[n for n in tree.body if not (isinstance(n,ast.ImportFrom) and n.module=='scripts' and any(a.name=='qd_ed_n23_v2_contract' for a in n.names))]
    module=types.ModuleType('test_only_n27_legacy_classifier');module.__file__=str(path);module.c=contract()
    exec(compile(tree,str(path),'exec'),module.__dict__)
    monkeypatch.setattr(recovery,'classifier',lambda:module)
    return module


def old_builders():
    path=runner.ROOT/'tests/test_qd_ed_n23_v2.py';tree=ast.parse(path.read_text())
    wanted={'write','failing_case','native_report','reservations'}
    tree.body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted]
    for n in tree.body:n.decorator_list=[]
    scope=dict(copy=copy,importlib=importlib,json=json,Path=Path,pytest=pytest,yaml=yaml,runner=runner,worker=worker,c=contract())
    exec(compile(tree,str(path),'exec'),scope)
    return types.SimpleNamespace(**scope)
