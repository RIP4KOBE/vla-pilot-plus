"""Load only this CPU draft; production files remain frozen until installation."""
import importlib.util
from pathlib import Path
import sys

import core

for name in ('stage_failed_contact_recheck', 'stage_evidence'):
    qualified = 'core.' + name
    spec = importlib.util.spec_from_file_location(qualified, Path(__file__).parent/'core'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    setattr(core, name, module)
