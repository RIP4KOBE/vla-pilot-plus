#!/usr/bin/env python3
"""GPU2 worker for explicit, separately reported RNG calibration comparisons."""
from pathlib import Path
import os
import sys

from c0_poe_resilient_worker import install as install_transport

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    install_transport()
    if '--cfg' not in sys.argv:
        import torch
        if os.environ.get('CUDA_VISIBLE_DEVICES') != '2':
            raise RuntimeError('This worker is assigned physical GPU2 only')
        total = torch.cuda.get_device_properties(0).total_memory
        torch.cuda.set_per_process_memory_fraction(min(1.,48*1024**3/total),device=0)
    sys.path.insert(0,str(ROOT))
    import hydra
    import main as main_module
    from core.episode_rng_hooks import install
    install(main_module)
    # Absolute config path keeps the same Hydra files when main is imported.
    entry = hydra.main(version_base=None,config_path=str(ROOT/'configs'),config_name='config')(main_module.main.__wrapped__)
    sys.argv[0] = str(ROOT/'main.py')
    entry()
