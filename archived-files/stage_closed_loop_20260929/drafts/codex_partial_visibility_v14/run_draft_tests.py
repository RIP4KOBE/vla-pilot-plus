"""Load candidate modules in this CPU process only; never edit live sources."""
import importlib.util
from pathlib import Path
import sys

ROOT=Path.cwd();DRAFT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));import core
for name in ('stage_evidence','stage_grasp_guard'):
    fullname='core.'+name
    spec=importlib.util.spec_from_file_location(fullname,DRAFT/'core'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);sys.modules[fullname]=module
    spec.loader.exec_module(module);setattr(core,name,module)
import pytest
raise SystemExit(pytest.main(['-q','--rootdir='+str(ROOT),'-p','no:cacheprovider',str(DRAFT/'test_partial_visibility.py'),
    'tests/test_stage_evidence.py','tests/test_stage_grasp_guard.py','tests/test_stage_robot_evidence.py',
    'tests/test_stage_recovery_priority.py','tests/test_stage_reward_progress_handoff.py',
    'tests/test_stage_reward_reference.py','tests/test_stage_carry_hold.py','tests/test_stage_carry_runtime.py',
    'tests/test_stage_gripper_passthrough.py','tests/test_stage_release_guard.py',
    'tests/test_stage_target_marker_runtime.py','tests/test_codex_online_observation.py']))
