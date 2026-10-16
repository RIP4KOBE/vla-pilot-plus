"""PI05 asset and protocol binding; the Stage/reward worker is shared with RDT."""
from pathlib import Path
import importlib.metadata
import json
import subprocess
import sys
import yaml
from scripts.steering_runtime import ROOT, digest, _merge_profile
from scripts.codex_only_runtime import validate_config


def load_local(path):
    local = yaml.safe_load(Path(path).read_text())
    required = ('pi05_checkpoint', 'pi05_tokenizer', 'torch_home', 'libero_root', 'libero_config')
    for key in required:
        p = Path(local[key]).expanduser().resolve()
        if not p.is_dir():
            raise ValueError(f'Missing directory {key}: {p}')
        local[key] = str(p)
    for key in ('gpu', 'egl_device_id'):
        if type(local[key]) is not int or local[key] < 0:
            raise ValueError(f'{key} must be a nonnegative integer')
    local.setdefault('allocator_limit_gib', 96)
    return local


def load_config(local, output_dir, tasks=None, *, source_root=ROOT):
    root = Path(source_root)
    cfg = yaml.safe_load((root/'configs/evaluation/libero_object_swap.yaml').read_text())
    _merge_profile(cfg, yaml.safe_load((root/'configs/steering/vls.yaml').read_text()))
    _merge_profile(cfg, yaml.safe_load((root/'configs/evaluation/libero_object_pi05.yaml').read_text()))
    all_tasks = cfg['backend']['libero']['task_ids_filter']
    seed_map = dict(zip(all_tasks, cfg['main']['episode_seed_schedule']))
    tasks = all_tasks if tasks is None else list(tasks)
    if tasks != sorted(set(tasks)) or not tasks or any(t not in seed_map for t in tasks):
        raise ValueError('Tasks must be sorted distinct LIBERO Object ids 0–9')
    out = Path(output_dir).resolve()
    cfg['main'].update(episode_num=len(tasks), episode_seed_schedule=[seed_map[t] for t in tasks])
    cfg['backend']['libero'].update(task_ids_filter=tasks, task_guide_scales=[80]*len(tasks))
    cfg['steering']['method'] = 'vls'
    cfg['main']['eds_eval'].update(method_label='pi05_vls', job_id=out.parent.name)
    cfg['policy']['pi05'].update(pretrained_path=local['pi05_checkpoint'],
        tokenizer_path=local['pi05_tokenizer'], metrics_path=str(out/'evaluation/pi05_metrics.jsonl'))
    cfg['perception']['vlm_agent']['query_template_dir'] = str(ROOT/'vlm_query/target_distance')
    cfg['hydra']['run']['dir'] = str(out)
    validate_config(cfg)
    return cfg


def verify_assets(local):
    """Verify PI05, tokenizer and DINO only; RDT encoders are not required."""
    expected = json.loads((ROOT/'scripts/public_model_sources.json').read_text())
    rows = []
    for key in ('pi05_checkpoint', 'pi05_tokenizer'):
        entry = expected['huggingface'][key]
        for item in entry['files']:
            p = Path(local[key])/item['path']
            if p.stat().st_size != item['bytes'] or digest(p) != item['sha256']:
                raise ValueError(f'Asset mismatch: {key}/{item["path"]}')
            rows.append(dict(root=key, **item))
        # Prevent a processor/model loader from selecting undeclared alternatives.
        allowed = {r['path'] for r in entry['files']}
        extra = {p.name for p in Path(local[key]).iterdir()
                 if p.is_file() and p.suffix in ('.json','.safetensors','.bin','.model')} - allowed
        if extra:
            raise ValueError(f'Unexpected loader inputs in {key}: {sorted(extra)}')
    base = json.loads((ROOT/'scripts/steering_model_assets_manifest.json').read_text())
    for item in base['files']:
        if item['root'] != 'torch_home':
            continue
        p = Path(local['torch_home'])/item['path']
        if p.stat().st_size != item['bytes'] or digest(p) != item['sha256']:
            raise ValueError(f'DINO asset mismatch: {item["path"]}')
        rows.append(item)
    prefix = Path(local['torch_home'])/'hub/facebookresearch_dinov2_main'
    expected_source = {r['path'].removeprefix('hub/facebookresearch_dinov2_main/')
                       for r in rows if r['root']=='torch_home'}
    unexpected = [str(p.relative_to(prefix)) for p in prefix.rglob('*')
                  if p.is_file() and p.suffix in ('.py','.so','.pyd')
                  and str(p.relative_to(prefix)) not in expected_source]
    if unexpected:
        raise ValueError(f'Unexpected DINO source: {unexpected}')
    return dict(valid=True, files=rows, bytes_hashed=sum(x['bytes'] for x in rows))


def environment_receipt(local):
    from scripts.prepare_steering_assets import verify_libero, verify_libero_paths
    from scripts.steering_dependency_compat import verify_runtime_compat
    revision = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT/'third_party/lerobot',text=True).strip()
    dirty = bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT/'third_party/lerobot',text=True))
    if revision != '715debf6c1723a28f1a57d4274a8c4ec35b6a417' or dirty:
        raise ValueError('LeRobot must be the clean pinned submodule')
    return dict(python=sys.version, python_executable=sys.executable,
        pip_freeze=subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True).splitlines(),
        packages={p:importlib.metadata.version(p) for p in ('torch','transformers','lerobot','numpy','mujoco','robosuite')},
        lerobot_commit=revision, codex_cli=subprocess.check_output(['codex','--version'],text=True).strip(),
        runtime_compatibility=verify_runtime_compat(), model_assets=verify_assets(local),
        libero=verify_libero(Path(local['libero_root'])), libero_paths=verify_libero_paths(local))
