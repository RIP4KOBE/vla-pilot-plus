import importlib.util
from pathlib import Path
import random
import numpy as np
import pytest
import torch

from core import episode_rng_fixture as rng
META=dict(task_id=3,episode_seed=546,phase='prepare')


def draw():
    return random.random(),np.random.normal(size=5),torch.randn(5)


def test_record_is_inert_and_restore_reproduces_all_cpu_streams(tmp_path):
    original=rng.capture()
    try:
        path=tmp_path/'rng.pt';before=rng.signature(rng.capture());proof=rng.record(path,META)
        assert rng.signature(rng.capture())==before
        expected=draw();draw();draw()
        rng.restore(path,META,proof['sha256']);actual=draw()
        assert actual[0]==expected[0] and np.array_equal(actual[1],expected[1]) and torch.equal(actual[2],expected[2])
    finally:
        random.setstate(original['python']);np.random.set_state(original['numpy']);torch.set_rng_state(original['torch_cpu'])


@pytest.mark.parametrize('field,value',[('task_id',8),('episode_seed',151),('phase','rollout')])
def test_wrong_task_seed_or_phase_cannot_mutate_rng(tmp_path,field,value):
    p=tmp_path/'rng.pt';proof=rng.record(p,META);before=rng.signature(rng.capture());wrong=dict(META);wrong[field]=value
    with pytest.raises(ValueError):rng.restore(p,wrong,proof['sha256'])
    assert rng.signature(rng.capture())==before


def test_hash_mismatch_and_existing_record_fail_closed(tmp_path):
    p=tmp_path/'rng.pt';proof=rng.record(p,META);before=rng.signature(rng.capture())
    with pytest.raises(ValueError):rng.restore(p,META,'0'*64)
    with pytest.raises(FileExistsError):rng.record(p,META)
    assert rng.digest(p)==proof['sha256'] and rng.signature(rng.capture())==before


def test_fixture_contains_rng_only(tmp_path):
    p=tmp_path/'rng.pt';rng.record(p,META);data=torch.load(p,weights_only=False)
    assert set(data)=={'schema','metadata','states'}
    assert set(data['states'])=={'python','numpy','torch_cpu','torch_cuda'}
