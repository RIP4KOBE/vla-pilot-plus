import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest


from core import episode_rng_hooks as hooks
from core import episode_rng_fixture as rng


@pytest.fixture
def fake_main(monkeypatch):
    monkeypatch.setitem(sys.modules, 'core.episode_rng_fixture', rng)
    class Main:
        def __init__(self, config):
            self.config = config
            self.adapter = SimpleNamespace(task_id=3)
            self.calls = []
        def perform_task_for_episode(self, episode_dir):
            self.calls.append(('prepare', episode_dir))
            return 'prepared'
        def _run_episode(self, episode, episode_dir, episode_seed):
            self.calls.append(('rollout', episode, episode_dir, episode_seed))
            return 'rolled'
    return SimpleNamespace(Main=Main, _adapter_actual_task_id=lambda a: a.task_id)


def test_default_hooks_do_not_touch_rng_or_require_schedule(fake_main, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('default path inspected RNG')
    monkeypatch.setattr(rng, 'capture', forbidden)
    hooks.install(fake_main)
    runner = fake_main.Main({})
    assert runner.perform_task_for_episode('unrestricted-path') == 'prepared'
    assert runner._run_episode(0, 'unrestricted-path', 546) == 'rolled'
    assert len(runner.calls) == 2


def test_prepare_and_rollout_record_real_task_and_explicit_seed(fake_main, tmp_path):
    hooks.install(fake_main)
    runner = fake_main.Main(dict(episode_rng_record_dir=str(tmp_path/'fixtures'), episode_seed_schedule=[546]))
    episode = tmp_path/'output/episode_1'
    before = rng.signature(rng.capture())
    runner.perform_task_for_episode(episode)
    runner._run_episode(0, episode, 546)
    assert rng.signature(rng.capture()) == before
    rows = [json.loads(x) for x in (tmp_path/'output/eds_eval/episode_rng_events.jsonl').read_text().splitlines()]
    assert [r['metadata'] for r in rows] == [dict(task_id=3, episode_seed=546, phase=p) for p in ('prepare','rollout')]
    assert len(runner.calls) == 2


def test_refuses_ambiguous_modes(fake_main, tmp_path):
    runner = fake_main.Main(dict(episode_rng_record_dir='record', episode_rng_fixture_manifest='restore'))
    with pytest.raises(ValueError, match='never both'):
        hooks.apply(runner, episode_dir=tmp_path/'episode_1', phase='prepare', task_id=3, episode_seed=546)


@pytest.mark.parametrize('valid,file', [(False, 'rng.pt'), (True,'../escaped.pt'), (True,'/absolute.pt')])
def test_rejects_unvalidated_calibration_and_escaping_paths(fake_main, tmp_path, valid, file):
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps(dict(schema='episode_rng_fixture_manifest_v1', calibration_valid=valid,
        fixtures={'3:prepare':dict(file=file,sha256='0'*64)})))
    runner = fake_main.Main(dict(episode_rng_fixture_manifest=str(manifest), episode_rng_fixture_manifest_sha256=rng.digest(manifest)))
    before = rng.signature(rng.capture())
    with pytest.raises(ValueError):
        hooks.apply(runner, episode_dir=tmp_path/'output/episode_1', phase='prepare', task_id=3, episode_seed=546)
    assert rng.signature(rng.capture()) == before


def test_restores_only_validated_hash_bound_fixture(fake_main, tmp_path):
    metadata = dict(task_id=3, episode_seed=546, phase='prepare')
    proof = rng.record(tmp_path/'rng.pt',metadata)
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps(dict(schema='episode_rng_fixture_manifest_v1',calibration_valid=True,
        fixtures={'3:prepare':dict(file='rng.pt',sha256=proof['sha256'])})))
    runner = fake_main.Main(dict(episode_rng_fixture_manifest=str(manifest), episode_rng_fixture_manifest_sha256=rng.digest(manifest)))
    hooks.apply(runner, episode_dir=tmp_path/'output/episode_1', phase='prepare', **{k:v for k,v in metadata.items() if k!='phase'})
    assert rng.signature(rng.capture()) == proof['state_signature']
    manifest.write_text(manifest.read_text()+'\n')
    with pytest.raises(ValueError, match='matching frozen'):
        hooks.apply(runner, episode_dir=tmp_path/'output/episode_1', phase='prepare', task_id=3, episode_seed=546)


def test_duplicate_install_fails(fake_main):
    hooks.install(fake_main)
    with pytest.raises(RuntimeError):
        hooks.install(fake_main)
