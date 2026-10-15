"""Exercise the existing wrapper tests against staged modules, original fixture roots."""
from pathlib import Path
import sys

stage = Path(__file__).resolve().parent
root = stage.parents[4]
sys.path.insert(0, str(stage / 'candidate'))
sys.path.append(str(root))
from scripts import audit_steering, steering_runtime, steering_worker
for module in (audit_steering, steering_runtime, steering_worker):
    module.ROOT = root
import pytest
raise SystemExit(pytest.main([str(root/'tests/test_steering_runner.py'), str(root/'tests/steering_audit/test_steering_contract_offline.py'), '-q', '--disable-warnings',
                            '-p', 'no:cacheprovider', '--basetemp=/tmp/steering-staged-wrapper-tests']))
