"""Initialization-only hooks installed by the steering worker.

Restore the recorded preparation and rollout random streams when configured.
The default path performs no RNG inspection, recording or restoration.
"""
import functools
import json
from pathlib import Path
import re


def apply(runner, *, episode_dir, phase, task_id, episode_seed):
    from core.episode_rng_fixture import record, restore, digest
    cfg = runner.config
    record_dir = cfg.get('episode_rng_record_dir')
    manifest_path = cfg.get('episode_rng_fixture_manifest')
    if record_dir and manifest_path:
        raise ValueError('Choose recording or restoration, never both')
    if not record_dir and not manifest_path:
        return
    metadata = dict(task_id=int(task_id), episode_seed=int(episode_seed), phase=phase)
    if record_dir:
        proof = record(Path(record_dir)/f'task_{task_id:02d}_{phase}.pt', metadata)
        mode = 'record'
    else:
        manifest_path = Path(manifest_path).resolve()
        expected_hash = cfg.get('episode_rng_fixture_manifest_sha256')
        if not expected_hash or digest(manifest_path) != expected_hash:
            raise ValueError('A matching frozen initialization manifest is required')
        manifest = json.loads(manifest_path.read_text())
        if manifest.get('schema') != 'episode_rng_fixture_manifest_v1' or manifest.get('calibration_valid') is not True:
            raise ValueError('Historical replay calibration must pass before restoration')
        entry = manifest['fixtures'][f'{task_id}:{phase}']
        relative = Path(entry['file'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Fixture paths must stay inside the calibration artifact')
        path = (manifest_path.parent/relative).resolve()
        if not path.is_relative_to(manifest_path.parent):
            raise ValueError('Fixture path escaped its calibration artifact')
        proof = restore(path, metadata, entry['sha256'])
        mode = 'historical_fixture_v1'
    evaluation = cfg.get('eds_eval', {}).get('output_dir')
    journal = (Path(evaluation) if evaluation else Path(episode_dir).parent/'eds_eval') / 'episode_rng_events.jsonl'
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open('a') as file:
        file.write(json.dumps(dict(mode=mode, **proof), sort_keys=True)+'\n')


def install(main_module):
    cls = main_module.Main
    if getattr(cls, '_episode_rng_hooks_installed', False):
        raise RuntimeError('Initialization hooks already installed')
    prepare = cls.perform_task_for_episode
    rollout = cls._run_episode

    @functools.wraps(prepare)
    def prepare_with_fixture(self, episode_dir):
        if self.config.get('episode_rng_record_dir') or self.config.get('episode_rng_fixture_manifest'):
            match = re.fullmatch(r'episode_(\d+)', Path(episode_dir).name)
            if match is None:
                raise ValueError('Unrecognized episode directory')
            schedule = self.config.get('episode_seed_schedule')
            if schedule is None:
                raise ValueError('Initialization comparison requires explicit environment seeds')
            index = int(match.group(1))-1
            apply(self, episode_dir=episode_dir, phase='prepare',
                  task_id=main_module._adapter_actual_task_id(self.adapter),
                  episode_seed=int(schedule[index]))
        return prepare(self, episode_dir)

    @functools.wraps(rollout)
    def rollout_with_fixture(self, episode, episode_dir, episode_seed):
        if self.config.get('episode_rng_record_dir') or self.config.get('episode_rng_fixture_manifest'):
            apply(self, episode_dir=episode_dir, phase='rollout',
                  task_id=main_module._adapter_actual_task_id(self.adapter), episode_seed=episode_seed)
        return rollout(self, episode, episode_dir, episode_seed)

    cls.perform_task_for_episode = prepare_with_fixture
    cls._run_episode = rollout_with_fixture
    cls._episode_rng_hooks_installed = True
