"""A separately named historical-initialization control protocol.

Only trusted, locally recorded RNG states are loaded. No environment state,
Stage replies, model actions, or generated reward functions are contained.
"""
import hashlib
from pathlib import Path
import random
import numpy as np
import torch

SCHEMA = 'episode_rng_fixture_v1'


def capture():
    # Never initialize CUDA just to inspect it (CPU diagnostics stay on CPU).
    return dict(python=random.getstate(), numpy=np.random.get_state(),
                torch_cpu=torch.get_rng_state(),
                torch_cuda=torch.cuda.get_rng_state_all() if torch.cuda.is_initialized() else [])


def signature(states):
    h = hashlib.sha256()
    h.update(repr(states['python']).encode())
    np_state = states['numpy']
    h.update(repr((np_state[0], *np_state[2:])).encode())
    h.update(np_state[1].tobytes())
    for value in [states['torch_cpu'], *states['torch_cuda']]:
        h.update(value.cpu().numpy().tobytes())
    return h.hexdigest()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record(path, metadata):
    path = Path(path)
    if set(metadata) != {'task_id', 'episode_seed', 'phase'} or metadata['phase'] not in {'prepare', 'rollout'}:
        raise ValueError('Explicit task, seed and supported phase are required')
    before = capture()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves prior calibration evidence.
    with path.open('xb') as file:
        torch.save(dict(schema=SCHEMA, metadata=dict(metadata), states=before), file)
    if signature(capture()) != signature(before):
        raise RuntimeError('Recording unexpectedly advanced the random stream')
    return dict(path=str(path), sha256=digest(path), metadata=dict(metadata),
                state_signature=signature(before), cuda_streams=len(before['torch_cuda']))


def restore(path, expected_metadata, expected_sha256):
    if digest(path) != expected_sha256:
        raise ValueError('Frozen RNG fixture hash differs')
    # These files are generated and hashed by this study, never external inputs.
    payload = torch.load(path, map_location='cpu', weights_only=False)
    if payload.get('schema') != SCHEMA or payload.get('metadata') != expected_metadata:
        raise ValueError('RNG fixture task/seed/phase mismatch')
    states = payload['states']
    current = capture()
    if len(states['torch_cuda']) != len(current['torch_cuda']):
        raise ValueError('CUDA random-stream count differs from calibration')
    random.setstate(states['python'])
    np.random.set_state(states['numpy'])
    torch.set_rng_state(states['torch_cpu'])
    if states['torch_cuda']:
        torch.cuda.set_rng_state_all(states['torch_cuda'])
    if signature(capture()) != signature(states):
        raise RuntimeError('Restored random states do not match the fixture')
    return dict(path=str(path), sha256=expected_sha256, metadata=dict(expected_metadata),
                state_signature=signature(states))
