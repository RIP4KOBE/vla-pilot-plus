"""Pytest-only read guard: static metadata/code and bounded synthetic fixtures."""
import json
import os
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
WORK=HERE/'validation_implementation'
SESSION=HERE.parents[1]
STATIC=set()
SOURCES=(WORK.resolve(),(SESSION/'study_worktree').resolve())
DATA=tuple((root/'data').resolve() for root in SOURCES)
STATES=tuple((root/'research-state.yaml').resolve() for root in SOURCES)
PLANS=(SESSION/'variants/n20_lift_quality_raw_binding/plan.frozen.v1.gpu7.json',
       SESSION/'variants/n21_stage_raw_reward_binding/plan.frozen.v1.gpu7.json',
       HERE/'plan.frozen.v1.gpu7.json')
ARTIFACTS={ (SESSION/'artifacts').resolve() }
for path in PLANS:
    value=json.loads(path.read_text())  # Explicitly allowed static Dev plan metadata.
    STATIC.add(path.resolve())
    for key in ('seed_plan_path','profiles_path','runtime_manifest_path'):
        STATIC.add(Path(value[key]).resolve())
    ARTIFACTS.add(Path(value['artifact_root']).resolve())
for root in SOURCES:
    STATIC.add((root/'data/frozen-seed-plan.json').resolve())
# Protocol metadata only; no result/status/Stage-event or native-evidence whitelist.
for path in [HERE/'protocol-dev-v1.md',HERE/'protocol-cpu-v1.md',HERE/'protocol-validation-conditional-v1.md',
 SESSION/'variants/n21_stage_raw_reward_binding/protocol-v1.md',
 SESSION/'variants/n21_stage_raw_reward_binding/gpu7-binding-addendum-v1.md',
 SESSION/'budget-autonomous-amendment-20260930-n22.md']:
    STATIC.add(path.resolve())
BLOCKED=[]


def guarded(path):
    path=Path(path).resolve()
    if path in STATIC:return False
    if path.is_relative_to(HERE) and any(part.startswith('validation-guarded-fixtures-') for part in path.parts):return False
    if any(path.is_relative_to(root) for root in DATA) or path in STATES:return True
    if any(path.is_relative_to(root) for root in SOURCES):return False  # Reviewed source/config/test bytes only.
    if any(path.is_relative_to(root) for root in ARTIFACTS):return True
    if path.is_relative_to(SESSION):
        # Imported helper source and prospective protocol files are not outcome evidence.
        return path.suffix not in {'.py','.pyc','.md'}
    return False


def hook(event,args):
    if event!='open' or isinstance(args[0],int):return
    path=args[0]
    if not isinstance(path,(str,bytes,os.PathLike)):return
    mode=args[1];flags=args[2]
    reading=not isinstance(mode,str) or 'r' in mode or '+' in mode
    if reading and guarded(os.fsdecode(path)):
        BLOCKED.append(str(Path(os.fsdecode(path)).resolve()))
        raise PermissionError('N22 CPU review path guard blocked historical/private data read')


sys.addaudithook(hook)


def pytest_sessionfinish(session,exitstatus):
    # Only guard metadata is printed, never attempted file contents.
    print('N22_CPU_PATH_GUARD '+json.dumps({'blocked_reads':len(BLOCKED),'blocked_paths':BLOCKED,
        'static_metadata_whitelist':sorted(str(p) for p in STATIC),'exitstatus':int(exitstatus)},sort_keys=True))
