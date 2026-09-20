import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
import torch
from safetensors.torch import save_file, load_file
from mode_gate import campaign
from mode_gate.candidates import compose_expansion_candidates, DeltaLineageEntry, PLANNER_UNIFORM
from mode_gate.experiment_contract import DEFAULT_RETRY_SCHEDULE_50

def test_planner_uniform_coefficients_apply_to_all_tensor_groups(tmp_path):
    base, delta = tmp_path/'base', tmp_path/'delta'
    base.mkdir(); delta.mkdir()
    # Use the actual checkpoint partition naming rules.
    tensors = {'model.paligemma_with_expert.paligemma.model.vision_tower.weight':torch.tensor([1.]),
               'model.paligemma_with_expert.paligemma.model.language_model.weight':torch.tensor([2.]),
               'model.action_in_proj.weight':torch.tensor([3.])}
    save_file(tensors, str(base/'model.safetensors'))
    save_file({k:torch.ones_like(v)*2 for k,v in tensors.items()},str(delta/'model.safetensors'))
    from mode_gate.checkpoint_math import checkpoint_digest
    (delta/'meta.json').write_text(json.dumps({'schema_version':'full-delta-v1', 'parent_checkpoint_digest':checkpoint_digest(base)}))
    grid=compose_expansion_candidates(theta0_checkpoint=base,parent_policy_id='v44',accepted_lineage=[],
        new_delta_id='d',new_delta_path=delta,output_root=tmp_path/'out',alpha_l_values=[.15,.7])
    for row, alpha in zip(grid['candidates'],[.15,.7]):
        assert row['alpha_map']==dict(vision=alpha,language=alpha,action=alpha)
        assert row['merge_method']==PLANNER_UNIFORM
        from mode_gate.checkpoint_math import CheckpointView, parameter_group
        assert {parameter_group(k) for k in tensors} == {'vision','language','action'}
        with CheckpointView(Path(row['checkpoint_path'])) as merged:
            for key, value in tensors.items():
                torch.testing.assert_close(merged.tensor(key),value+2*alpha)
    with pytest.raises(ValueError,match='uniform'):
        DeltaLineageEntry('d',str(delta),alpha_l=.2)

def test_scope_is_environment_position_twenty_only():
    tasks=[{'task_key':f'{variant}-{i}','perturbation_variant':variant} for variant in
           ('use_environment','use_swap','use_language','use_object') for i in range(10)]
    actual=campaign.selected_tasks({'tasks':tasks})
    assert len(actual)==20
    assert {x['perturbation_variant'] for x in actual}=={'use_environment','use_swap'}
    with pytest.raises(ValueError):
        campaign.selected_tasks({'tasks':tasks[1:]})

def test_baseline_steering_is_applied_at_every_retry(tmp_path, monkeypatch):
    from omegaconf import OmegaConf
    keys={'guide_scale':40.,'guide_scale_max':80.,'diversity_scale':10.,'diversity_scale_max':20.,
          'MCMC_steps':4,'sigmoid_k':25.,'sigmoid_x0':.75,'start_ratio':None,
          'use_fkd':True,'use_diversity':True,'fkd':{'lmbda':10.,'resample_frequency':5}}
    source=tmp_path/'source.json'; template=tmp_path/'template.json'
    source.write_text(json.dumps({'method':'v44_vls','sample_count':40,'stage_query_limit':50,
        'max_episode_steps':720,'inference_steps':10,'execution_horizon':10,'checkpoint':'v44','tokenizer':'pali',
        'num_steps_wait':5,'observation_width':128,'observation_height':128}))
    template.write_text(json.dumps({'main':keys}))
    (tmp_path/'episode_001').mkdir()
    (tmp_path/'episode_001/chunks.jsonl').write_text(json.dumps({'guide_scale':80.})+'\n')
    monkeypatch.setattr(campaign,'configuration',lambda:{'baseline_config':str(source),'baseline_runtime':str(template)})
    cfg=OmegaConf.create({'main':{},'policy':{'pi05':{}},'backend':{'libero':{}},'mode_gate':{}})
    # Hydra's real backend is structured; the new explicit task scales must be insertable.
    OmegaConf.set_struct(cfg.backend.libero, True)
    campaign.apply_baseline_steering(cfg)
    assert cfg.main.sample_batch_size==40 and cfg.main.guide_scale==80 and cfg.main.diversity_scale==10
    assert list(cfg.backend.libero.task_guide_scales)==[80.]*10
    assert cfg.policy.pi05.num_inference_steps==10 and cfg.backend.libero.max_episode_steps==720
    assert tuple(map(tuple,cfg.mode_gate.retry_schedule))==DEFAULT_RETRY_SCHEDULE_50==((1.,1.),)*50


def test_user_fixed_merge_selection_skips_account_request(tmp_path):
    from mode_gate.experience_planner import ExperiencePlanner
    from mode_gate.incidents import IncidentMemory
    def forbidden(**kwargs):
        pytest.fail('fixed alpha must not request a Planner coefficient search')
    selection = ExperiencePlanner(IncidentMemory(tmp_path), client=SimpleNamespace(request=forbidden)).choose_merge_coefficients({})
    assert selection['alpha_values'] == [.8]
    assert selection['alpha_map'] == dict(language=.8, vision=.8, action=.8)
    assert selection['selection_owner'] == 'user_configuration' and selection['search_enabled'] is False


@pytest.mark.parametrize('alpha', [float('nan'), float('inf'), -.1, 1.1, True])
def test_fixed_merge_setting_is_validated_without_hardcoding_coefficient(alpha, monkeypatch):
    monkeypatch.setattr(campaign, 'configuration', lambda: {'merge_coefficients': {'mode': 'fixed_uniform', 'alpha': alpha}})
    with pytest.raises(ValueError, match='alpha'):
        campaign.configured_merge_selection()


def test_new_delta_and_reuse_only_compose_point_eight_even_with_old_cached_grid(tmp_path, monkeypatch):
    from mode_gate.checkpoint_math import checkpoint_digest, CheckpointView
    from mode_gate.registry import PolicyRegistry
    from mode_gate.incidents import IncidentMemory
    from mode_gate.slow_loop import SlowLoopStore, SlowLoopJob, SlowLoopState
    from mode_gate.slow_worker import SlowLoopWorker
    from mode_gate.experience_planner import ExperiencePlanner
    from mode_gate.io_utils import sha256_file
    base, trained = tmp_path/'base', tmp_path/'trained'
    base.mkdir(); trained.mkdir()
    tensors = {'model.paligemma_with_expert.paligemma.model.vision_tower.weight':torch.tensor([1.]),
               'model.paligemma_with_expert.paligemma.model.language_model.weight':torch.tensor([2.]),
               'model.action_in_proj.weight':torch.tensor([3.])}
    save_file(tensors, str(base/'model.safetensors'))
    save_file({k:v+2 for k,v in tensors.items()}, str(trained/'model.safetensors'))
    registry = PolicyRegistry(tmp_path/'registry')
    registry.initialize_base(checkpoint_path=str(base), digest=checkpoint_digest(base), metadata={})
    registry.install_artifact('policy', 'parent', base)
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'schema_version':'joint-eval-manifest-v1', 'manifest_sha256':'m', 'tasks':[]}))
    worker = SlowLoopWorker(store=SlowLoopStore(tmp_path/'slow'), registry=registry,
        incidents=IncidentMemory(tmp_path/'incidents'), protocol_manifest=manifest,
        ticket_root=tmp_path/'tickets', work_root=tmp_path/'work')
    job = SlowLoopJob('job', SlowLoopState.DELTA_READY, 'parent', 'ticket', 'input', None, 1,
        {'theta_ft_checkpoint_path':str(trained), 'theta_ft_checkpoint_digest':checkpoint_digest(trained),
         'cleanup_theta_ft':False, 'coft_source_manifest_path':'unchanged-sft-sources'})
    cached = tmp_path/'work/job/merge_selection.json'
    cached.parent.mkdir(parents=True)
    cached.write_text(json.dumps({'alpha_values':[.2,.4,.6], 'reason':'old unconsumed suggestion'}))
    def forbidden(*args, **kwargs):
        pytest.fail('worker must honor fixed config before cached/Planner coefficient search')
    monkeypatch.setattr(ExperiencePlanner, 'choose_merge_coefficients', forbidden)
    outcome = worker._extract_delta_and_candidates(job)
    candidates = json.loads(Path(outcome.metadata['candidates_json_path']).read_text())
    assert len(candidates) == 1 and candidates[0]['alpha_map'] == dict(language=.8, vision=.8, action=.8)
    assert json.loads(cached.read_text())['alpha_values'] == [.8]
    assert cached in outcome.artifacts
    with CheckpointView(Path(candidates[0]['checkpoint_path'])) as merged:
        for key, value in tensors.items():
            torch.testing.assert_close(merged.tensor(key), value + .8*2)
    assert worker._extract_delta_and_candidates(job).metadata['candidate_grid_path'] == outcome.metadata['candidate_grid_path']
    # A historical lookup's old alpha is evidence, not the current experiment's coefficient.
    report = tmp_path/'historical-test.json'
    report.write_text(json.dumps({'native_successes':8, 'episodes':10}))
    lookup = tmp_path/'lookup.json'
    lookup.write_text(json.dumps({'active_policy_id':'parent', 'alpha_l_values':[.2,.6,1.],
        'remedy':{'delta_id':outcome.metadata['delta_id'], 'metadata':{
            'delta_digest':checkpoint_digest(outcome.metadata['registered_delta_path']),
            'policy_gate_report_path':str(report), 'policy_gate_report_sha256':sha256_file(report)}}}))
    lookup_hash = sha256_file(lookup)
    reuse_job = SlowLoopJob('reuse', SlowLoopState.REUSE_EVALUATING, 'parent', 'ticket', 'input2', None, 1,
        {'lookup_result_path':str(lookup), 'lookup_result_sha256':lookup_hash})
    monkeypatch.setattr(worker, '_prepare_policy_gate', lambda value: SimpleNamespace(metadata=value.metadata))
    reused = worker._prepare_reuse(reuse_job)
    reuse_candidates = json.loads(Path(reused.metadata['candidates_json_path']).read_text())
    assert len(reuse_candidates) == 1 and reuse_candidates[0]['alpha_map'] == dict(language=.8, vision=.8, action=.8)
    assert sha256_file(lookup) == lookup_hash
    assert reused.metadata['merge_coefficient_selection']['alpha_values'] == [.8]


@pytest.mark.parametrize('has_old', [True, False])
def test_fixed_alpha_does_not_change_sft_source_mixture(has_old):
    from mode_gate.training import SourceAwareSampler
    sampler = SourceAwareSampler(new_indices=[0], old_ticket_indices={'old':[1]} if has_old else {},
                                 replay_indices=[2], num_samples=1000, seed=7)
    expected = dict(new=.5, old=.25, replay=.25) if has_old else dict(new=.5, old=0., replay=.5)
    assert sampler.source_masses == expected
    draws = list(sampler)
    assert [draws.count(i) for i in (0,1,2)] == [round(1000*expected[k]) for k in ('new','old','replay')]


def test_fixed_selection_survives_policy_gate_handoff(tmp_path, monkeypatch):
    from mode_gate.slow_worker import SlowLoopWorker
    from mode_gate.slow_loop import SlowLoopJob, SlowLoopState
    worker = SlowLoopWorker.__new__(SlowLoopWorker)
    worker.work_root = tmp_path
    worker.protocol_manifest_path = tmp_path/'manifest.json'
    worker.protocol_manifest = {'manifest_sha256':'m'}
    monkeypatch.setattr(worker, '_require_current_task_training', lambda job: {'verified':'current-task'})
    fixed = campaign.configured_merge_selection()
    selection_path = tmp_path/'reuse_merge_selection.json'
    selection_path.write_text(json.dumps(fixed))
    job = SlowLoopJob('gate', SlowLoopState.ALPHA_SELECTING, 'parent', 'ticket', 'i', None, 1,
        {'ticket_path':str(tmp_path/'ticket.json'), 'parent_candidate_path':str(tmp_path/'parent.json'),
         'candidates_json_path':str(tmp_path/'candidates.json'), 'merge_selection_path':str(selection_path),
         'merge_coefficient_selection':fixed, 'gate_kind':'REUSE'})
    result = worker._prepare_policy_gate(job)
    spec = json.loads(Path(result.metadata['policy_gate_job_path']).read_text())
    assert spec['merge_coefficient_selection'] == fixed == result.metadata['merge_coefficient_selection']
    assert selection_path in result.artifacts and '--reuse' in spec['command']
