"""Explicit, separately recorded environment or managed-login service probes."""
from __future__ import annotations

import argparse
import base64
import io
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.steering_runtime import atomic_json, load_local, runtime_environment, utc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-config', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--api', action='store_true', help='Make one real Codex image request')
    parser.add_argument('--gpu', action='store_true', help='Check CUDA and render the task environment')
    args = parser.parse_args()
    local = load_local(args.local_config)
    destination = Path(args.output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    report = {'started_at': utc(), 'kind': 'preflight_not_performance', 'status': 'running'}
    atomic_json(destination / 'report.json', report)
    import os
    env = runtime_environment(local)
    os.environ.clear()
    os.environ.update(env)
    for path in reversed(env['PYTHONPATH'].split(os.pathsep)):
        if path not in sys.path:
            sys.path.insert(0, path)
    try:
        if args.api:
            from PIL import Image
            from core.codex_vision import CodexVisionTransport
            stream = io.BytesIO()
            Image.new('RGB', (96, 96), (255, 0, 0)).save(stream, format='PNG')
            uri = 'data:image/png;base64,' + base64.b64encode(stream.getvalue()).decode()
            transport = CodexVisionTransport(dict(
                backend='codex_cli', model='gpt-6-astra', reasoning_effort='low',
                timeout_seconds=180, transport_retry_count=1,
                event_policy='completed_transport_cycles_v6',
                capture_dir=str(destination / 'api_requests')))
            answer = transport._request_stage_response([
                {'type': 'text', 'text': 'Identify the solid color in the image. Reply only with the color name in lowercase.'},
                {'type': 'image_url', 'image_url': {'url': uri}}])
            report['api'] = {'response': answer, 'valid': answer.strip().lower() == 'red',
                             'model': transport.model, 'reasoning_effort': transport.reasoning_effort,
                             'counter': transport.api_request_counter.snapshot()}
            if not report['api']['valid']:
                raise RuntimeError('Codex image probe returned an unexpected answer')
        if args.gpu:
            import torch
            if not torch.cuda.is_available():
                raise RuntimeError('CUDA unavailable')
            value = torch.ones(32, device='cuda').square().sum().item()
            report['gpu'] = {'physical_gpu': local['gpu'], 'egl_device_id': local['egl_device_id'],
                             'name': torch.cuda.get_device_name(0), 'torch': torch.__version__,
                             'cuda': torch.version.cuda, 'tensor_probe': value}
            import libero
            import libero.libero.benchmark as benchmark
            from libero.libero.envs import OffScreenRenderEnv
            suite = benchmark.get_benchmark_dict()['libero_object_swap']()
            task = suite.get_task(0)
            from libero.libero import get_libero_path
            task_path = Path(get_libero_path('bddl_files')) / task.problem_folder / task.bddl_file
            environment = OffScreenRenderEnv(bddl_file_name=str(task_path), camera_heights=128,
                                             camera_widths=128)
            try:
                obs = environment.reset()
                report['render'] = {'libero_module': libero.__file__, 'task': task.name,
                                    'image_shape': list(obs['agentview_image'].shape)}
            finally:
                environment.close()
        report.update(status='pass', completed_at=utc())
    except Exception as exc:
        report.update(status='fail', error_type=type(exc).__name__, completed_at=utc())
        atomic_json(destination / 'report.json', report)
        raise
    atomic_json(destination / 'report.json', report)
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
