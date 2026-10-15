#!/usr/bin/env python3
"""Poe transport launcher with a GPU2 allocator ceiling for safe co-residency."""
from pathlib import Path
import os
import runpy
import sys

from c0_poe_resilient_worker import install

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    install()
    if '--cfg' not in sys.argv:
        import torch
        if os.environ.get('CUDA_VISIBLE_DEVICES') != '2':
            raise RuntimeError('This worker is assigned physical GPU2 only')
        ceiling = 48 * 1024**3
        total = torch.cuda.get_device_properties(0).total_memory
        torch.cuda.set_per_process_memory_fraction(min(1., ceiling/total), device=0)
    sys.argv[0] = str(ROOT/'main.py')
    runpy.run_path(str(ROOT/'main.py'), run_name='__main__')
