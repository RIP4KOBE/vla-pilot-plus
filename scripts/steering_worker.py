"""Run the frozen config through the existing main and two-phase RNG hooks."""
from __future__ import annotations

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    if os.environ.get('VLA_CODEX_ONLY') != '1':
        raise RuntimeError('Use scripts/run_steering.py to construct the online runtime')
    config_path = Path(sys.argv[1]).resolve()
    hydra_args = sys.argv[2:]
    if '--cfg' not in hydra_args:
        import json
        from scripts.steering_runtime import digest, source_unchanged
        manifest = json.loads((config_path.parent / 'manifest.json').read_text())
        if digest(config_path) != manifest['config_sha256'] or not source_unchanged(manifest['source_sha256']):
            raise RuntimeError('Frozen config or runtime source changed before worker start')
        if manifest.get('schema') in ('steering_cohort_v2', 'pi05_vls_cohort_v1'):
            if manifest['schema'] == 'pi05_vls_cohort_v1':
                from scripts.pi05_runtime import load_local
            else:
                from scripts.steering_runtime import load_local
            from scripts.prepare_steering_assets import verify_libero_paths
            local_path = config_path.parent / 'local-config.yaml'
            if digest(local_path) != manifest['local_config_sha256']:
                raise RuntimeError('Frozen local configuration changed before worker start')
            environment = json.loads((config_path.parent / 'environment.json').read_text())
            if verify_libero_paths(load_local(local_path)) != environment['libero_paths']:
                raise RuntimeError('LIBERO asset path configuration changed before worker start')
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError('CUDA is unavailable; no CPU substitute for the online cohort')
        ceiling = float(os.environ.get('VLA_STEERING_ALLOCATOR_GIB', '48')) * 1024**3
        torch.cuda.set_per_process_memory_fraction(
            min(1., ceiling / torch.cuda.get_device_properties(0).total_memory), device=0)
    import hydra
    import main as main_module
    from core.episode_rng_hooks import install
    install(main_module)
    entry = hydra.main(version_base=None, config_path=str(config_path.parent),
                       config_name=config_path.stem)(main_module.main.__wrapped__)
    sys.argv = [str(ROOT / 'main.py'), *hydra_args]
    entry()


if __name__ == '__main__':
    main()
