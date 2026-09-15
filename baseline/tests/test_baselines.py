"""CPU contract tests; no simulator, model checkpoint, or production files."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from torch import nn

from baseline.config import load_config
from baseline.io import safe_output, write_json
from baseline.protocol import Protocol
from baseline.methods.clare import Clare, ExpandableFFN
from baseline.methods.mlr_ifa import ByteReplay, angular_margin_loss, selected_similar_pairs
from baseline.methods.continual_rl import LoRALinear, gaussian_log_prob, grpo_loss, group_advantages
from baseline.methods.rl2_vla import QAM, conformal_threshold, compose_velocity


def protocol_file(tmp_path):
    tasks = []
    for i in range(40):
        tasks.append({"task_key": f"task-{i}", "task_id": f"task-{i}", "task_index": i % 10,
                      "suite": "libero_goal", "runtime_suite": "libero_goal_lan", "perturbation_variant": "use_language",
                      "benchmark": "LIBERO-PRO", "splits": {"demo_online_pool": list(map(str, range(7))),
                      "fixed_development_probe": ["7", "8"], "policy_alpha_selection": ["9"],
                      "policy_regression": ["10"], "policy_final_sealed": ["11"]}})
    value = {"tasks": tasks}
    value["manifest_sha256"] = hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    path = tmp_path / "protocol.json"
    write_json(path, value)
    return path


def test_config_is_independent_and_typos_fail():
    one = load_config(overrides={"clare": {"bottleneck": 8}})
    assert load_config()["clare"]["bottleneck"] == 128
    assert one["clare"]["bottleneck"] == 8
    with pytest.raises(ValueError):
        load_config(overrides={"clare": {"bottleneck_typo": 8}})


def test_outputs_never_overlap_live_artifacts_or_overwrite(tmp_path):
    with pytest.raises(ValueError):
        safe_output(tmp_path / "self_improve" / "replay", "test")
    with pytest.raises(ValueError):
        safe_output(tmp_path, "../escape")
    safe_output(tmp_path, "new")
    with pytest.raises(FileExistsError):
        safe_output(tmp_path, "new")


def test_protocol_is_paired_and_sealed(tmp_path):
    p = Protocol(protocol_file(tmp_path))
    assert p.contexts("fixed_development_probe", 7) == p.contexts("fixed_development_probe", 7)
    assert len(p.contexts("fixed_development_probe", 7)) == 80
    with pytest.raises(ValueError):
        p.contexts("policy_final_sealed", 7)
    with pytest.raises(ValueError):
        p.validate_training_source({"task_key": "task-0", "split": "demo_online_pool", "init_state_ids": ["7"]})


def test_collection_roles_separate_states(tmp_path):
    from baseline.rollout import collection_roles
    p = Protocol(protocol_file(tmp_path))
    roles = collection_roles(p, 23)
    assert {role for role, _ in roles} == {"train", "calibration", "validation"}
    assert len({(c["task_key"], c["init_state_id"]) for _, c in roles}) == len(roles)


def test_byte_replay_is_balanced_and_excludes_unretained_data():
    memory = ByteReplay(400, 9)
    a = [{"path": f"a{i}", "task_key": "a", "bytes": 100} for i in range(4)]
    b = [{"path": f"b{i}", "task_key": "b", "bytes": 100} for i in range(4)]
    memory.update(a)
    memory.update(b)
    assert memory.bytes == 400
    assert sum(v["task_key"] == "a" for v in memory.entries) == 2
    assert sum(v["task_key"] == "b" for v in memory.entries) == 2
    with pytest.raises(ValueError):
        ByteReplay(99, 9).update(a)


def test_ifa_has_a_real_gradient_and_requires_selected_pairs():
    feature = torch.tensor([[-0.2, 1.0]], requires_grad=True)
    prototypes = {"a": {"language": torch.tensor([1., 0.]), "visual": torch.tensor([1., 0.])},
                  "b": {"language": torch.tensor([0., 1.]), "visual": torch.tensor([1., 0.])}}
    loss = angular_margin_loss(feature, ["a"], prototypes, {("a", "b")}, 0.72)
    loss.backward()
    assert loss > 0 and feature.grad.abs().sum() > 0
    assert angular_margin_loss(feature, ["a"], prototypes, set(), 0.72) == 0
    assert selected_similar_pairs(prototypes, 0.5) == {("a", "b")}


class ToyFFN(nn.Module):
    def __init__(self):
        super().__init__()
        self.up_proj = nn.Linear(4, 8)
        self.down_proj = nn.Linear(8, 4)

    def forward(self, x):
        return self.down_proj(self.up_proj(x).relu())


class ToyPolicy(nn.Module):
    def __init__(self):
        super().__init__()
        self.layers = nn.ModuleList([nn.Module(), nn.Module()])
        for layer in self.layers:
            layer.mlp = ToyFFN()

    def forward(self, x):
        for layer in self.layers:
            x = x + layer.mlp(x)
        return x


def test_clare_old_adapters_frozen_and_restore_preserves_predictions():
    torch.manual_seed(3)
    policy = ToyPolicy()
    runtime = SimpleNamespace(model=SimpleNamespace(paligemma_with_expert=SimpleNamespace(gemma_expert=SimpleNamespace(model=policy))))
    cfg = {**load_config()["clare"], "bottleneck": 2, "ae_hidden": 4, "ae_latent": 2,
           "feature_batches": 2, "discriminator_steps": 2}
    method = Clare(runtime, cfg)
    x = torch.randn(3, 2, 4)
    forward = lambda: policy(x).square().mean()
    method.train_stage("a", forward, steps=2, learning_rate=1e-3, max_norm=1, report=lambda _: None)
    before = [copy.deepcopy(layer.adapters[0].state_dict()) for layer in method.layers.values()]
    method.train_stage("b", forward, steps=2, learning_rate=1e-3, max_norm=1, report=lambda _: None)
    for layer, weights in zip(method.layers.values(), before):
        assert all(torch.equal(value, layer.adapters[0].state_dict()[k]) for k, value in weights.items())
    expected = policy(x).detach()
    state = method.state()
    for layer in policy.layers:
        layer.mlp = layer.mlp.base
    restored = Clare(runtime, cfg)
    restored.restore(state)
    assert torch.equal(expected, policy(x))


def test_lora_preserves_initial_policy_then_updates_only_low_rank_branch():
    base = nn.Linear(4, 5)
    original = copy.deepcopy(base.state_dict())
    layer = LoRALinear(base, 2, 2)
    x = torch.randn(3, 4)
    assert torch.equal(layer(x), base(x))
    layer(x).square().mean().backward()
    assert base.weight.grad is None
    assert layer.b.weight.grad.abs().sum() > 0
    assert torch.equal(original["weight"], base.weight)


def test_grpo_density_ratio_is_one_and_gradient_is_not_bc():
    mean = torch.zeros(2, 3, 4, requires_grad=True)
    y = torch.ones_like(mean)
    old = gaussian_log_prob(y, mean.detach(), 0.1)
    new = gaussian_log_prob(y, mean, 0.1)
    assert torch.equal((new - old).exp(), torch.ones(2, dtype=torch.float64))
    loss = grpo_loss(new, old, torch.tensor([1., -1.]), 0.2)
    loss.backward()
    assert mean.grad[0].mean() < 0 < mean.grad[1].mean()
    assert torch.equal(group_advantages([0, 0, 0]), torch.zeros(3))


def test_qam_has_td_and_adjoint_updates_and_frozen_targets():
    torch.manual_seed(11)
    cfg = {**load_config()["rl2_vla"], "hidden_dim": 8, "hidden_layers": 2, "flow_steps": 3}
    model = QAM(4, 7, cfg)
    batch = {"latent": torch.randn(3, 4), "next_latent": torch.randn(3, 4),
             "actions": torch.randn(3, 7), "reward": torch.tensor([0., 1., 0.]),
             "bootstrap_discount": torch.tensor([0.9, 0., 0.9])}
    loss, metrics = model.losses(batch)
    loss.backward()
    assert torch.isfinite(loss) and metrics["adjoint_loss"] > 0
    assert sum(float(p.grad.abs().sum()) for p in model.fast.parameters()) > 0
    assert all(p.grad is None for p in model.target_slow.parameters())
    assert all(p.grad is None for p in model.target_critic.parameters())


def test_composition_has_correct_opposite_time_direction_and_preserves_padding():
    base = torch.ones(2, 50, 32)
    qam = torch.full((2, 70), 2.0)
    mixed = compose_velocity(base, qam, torch.tensor([0., 1.]), 10)
    assert torch.equal(mixed[0, :10, :7], torch.full((10, 7), -2.0))
    assert torch.equal(mixed[1], base[1])
    assert torch.equal(mixed[:, 10:], base[:, 10:])
    assert torch.equal(mixed[..., 7:], base[..., 7:])


def test_conformal_band_uses_episode_maxima_and_refuses_too_few_successes():
    assert conformal_threshold([[.1, .3], [.2, .4], [.1, .2]], .25) == pytest.approx(.4)
    with pytest.raises(ValueError):
        conformal_threshold([[.1, .3]], .1)


def test_continual_metrics_detect_forgetting():
    from baseline.evaluation import continual_metrics
    result = continual_metrics([[.9, .1], [.6, .8]])
    assert result["forgetting"] == pytest.approx(.3)
    assert result["backward_transfer"] == pytest.approx(-.3)
    with pytest.raises(ValueError):
        continual_metrics([[float("nan")]])


def test_shared_gpu_allowed_when_memory_is_sufficient_but_replay_is_protected(tmp_path, monkeypatch):
    from baseline import resources
    monkeypatch.setattr(resources, "__file__", str(tmp_path / "resources.py"))
    monkeypatch.setattr(resources.subprocess, "check_output", lambda *a, **k: "7, GPU-test-7, 70000\n6, GPU-test-6, 70000\n")
    cfg = load_config()
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "7")
    with resources.isolated_device(cfg):
        import os
        assert os.environ["CUDA_VISIBLE_DEVICES"] == "GPU-test-7"
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "6")
    with pytest.raises(RuntimeError, match="reserved for replay"):
        with resources.isolated_device(cfg):
            pass
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "7")
    cfg["gpu_min_free_mib"] = 80000
    with pytest.raises(RuntimeError, match="model not loaded"):
        with resources.isolated_device(cfg):
            pass


def test_latent_cache_rejects_changed_or_wrong_base_records(tmp_path):
    from baseline.demonstration_inputs import CONTRACT
    from baseline.data import latent_batch
    from baseline.io import save_tensors, digest
    path = tmp_path / "latent.pt"
    record = {"base_identity": "v44", "task_key": "a", "embedded": {"embeddings": torch.ones(1, 2, 3)},
              "actions": torch.ones(1, 50, 7), "padding": None, "input_contract": CONTRACT,
              "source_conversion_sha256": "conversion"}
    save_tensors(path, record)
    index = [{"path": str(path), "base_identity": "v44", "task_key": "a", "sha256": digest(path),
              "input_contract": CONTRACT, "source_conversion_sha256": "conversion"}]
    assert latent_batch(index, "cpu", "v44")[1].shape == (1, 50, 7)
    with pytest.raises(ValueError):
        latent_batch(index, "cpu", "other-checkpoint")
    save_tensors(path, {**record, "actions": torch.zeros(1, 50, 7)})
    with pytest.raises(ValueError):
        latent_batch(index, "cpu", "v44")


def test_stage_restore_verifies_base_protocol_and_algorithm(tmp_path):
    from baseline.artifacts import save_stage, load_stage
    runtime = SimpleNamespace(identity={"sha256": "v44"})
    protocol = SimpleNamespace(digest="protocol")
    received = []
    method = SimpleNamespace(stages=["a"], state=lambda: {"weights": torch.ones(2)}, restore=received.append)
    cfg = load_config()
    stage = save_stage(tmp_path, 0, method, runtime, protocol, cfg)
    assert load_stage(stage, runtime, protocol, method, cfg)["state_bytes"] > 0
    assert torch.equal(received[0]["weights"], torch.ones(2))
    wrong = load_config(overrides={"inference_steps": 5})
    with pytest.raises(ValueError, match="policy contract"):
        load_stage(stage, runtime, protocol, method, wrong)
    wrong = load_config(overrides={"clare": {"expansion_threshold": 10}})
    with pytest.raises(ValueError, match="algorithm settings"):
        load_stage(stage, runtime, protocol, method, wrong)
    with pytest.raises(ValueError, match="identity differs"):
        load_stage(stage, SimpleNamespace(identity={"sha256": "different"}), protocol, method, cfg)


def test_accumulation_matches_one_effective_batch_of_32():
    from baseline.optimization import accumulated_step
    torch.manual_seed(7)
    model = nn.Linear(3, 1)
    full = copy.deepcopy(model)
    x, y = torch.randn(32, 3), torch.randn(32, 1)
    optimizer = torch.optim.SGD(model.parameters(), lr=.01)
    batches = iter(zip(x.split(4), y.split(4)))
    calls = []
    def forward():
        xx, yy = next(batches)
        calls.append(len(xx))
        return (model(xx) - yy).square().mean(), {}
    accumulated_step(forward, list(model.parameters()), optimizer, 8, 1000)
    reference = torch.optim.SGD(full.parameters(), lr=.01)
    (full(x) - y).square().mean().backward()
    reference.step()
    assert calls == [4] * 8
    for p, q in zip(model.parameters(), full.parameters()):
        torch.testing.assert_close(p, q)


def test_main_optimizer_schedule_is_not_rescaled():
    from baseline.optimization import policy_optimizer
    cfg = load_config()
    model = nn.Linear(2, 1)
    optimizer, scheduler = policy_optimizer(list(model.parameters()), cfg)
    assert optimizer.defaults['betas'] == (.9, .95)
    assert optimizer.defaults['weight_decay'] == 1e-10
    assert optimizer.param_groups[0]['lr'] == pytest.approx(2.5e-5 / 1001)
    optimizer.step()
    scheduler.step()
    assert optimizer.param_groups[0]['lr'] < 1e-7
    with pytest.raises(ValueError, match='global_batch_size'):
        load_config(overrides={'gradient_accumulation_steps':1})


def test_frozen_main_plan_preserves_context_order_and_two_seeds(tmp_path):
    from baseline.experiment import main_contexts, task_order
    p = Protocol(protocol_file(tmp_path))
    rows = []
    for i, key in enumerate(reversed(sorted(p.tasks))):
        rows.append({**{k:v for k,v in p.tasks[key].items() if k!='splits'},
                     'context_id':str(i),'source_split':'demo_online_pool', 'init_state_id':'0',
                     'env_seed':123+i, 'policy_seed':987654321234+i})
    path = tmp_path/'main_plan.json'
    write_json(path, {'manifest_sha256':p.digest, 'task_count':40,'contexts':rows})
    cfg = load_config(overrides={'experiment_plan':str(path)})
    actual = main_contexts(cfg, p)
    assert task_order(cfg,p) == [r['task_key'] for r in rows]
    assert actual[0]['seed']==123 and actual[0]['policy_seed']==987654321234
    rows[0]['init_state_id']='11'
    write_json(path, {'manifest_sha256':p.digest,'task_count':40,'contexts':rows})
    with pytest.raises(ValueError, match='sealed states'):
        main_contexts(cfg,p)


def test_bounded_rollout_keeps_simulator_horizon_and_closes_environment(monkeypatch):
    from baseline import rollout
    calls = []
    adapter = SimpleNamespace(get_policy_observation=lambda **kw: {},
                              step=lambda action: ({}, 0., False, False, {}),
                              _get_current_robosuite_env=lambda:SimpleNamespace(done=False,timestep=0,horizon=720),
                              close=lambda: calls.append('closed'))
    monkeypatch.setattr(rollout, 'make_environment', lambda cfg, ctx: (calls.append(cfg['max_episode_steps']) or adapter))
    monkeypatch.setattr(rollout, 'reset_environment', lambda env, ctx: {})
    runtime = SimpleNamespace(policy=SimpleNamespace(reset=lambda: None), preprocess=lambda raw: raw,
                              embed=lambda x:x, prefix=lambda x:x, sample=lambda x:torch.zeros(1,50,7),
                              physical=lambda x:x)
    summary, _ = rollout.episode(runtime, load_config(), {'seed':1}, max_policy_steps=3)
    assert summary['steps'] == 3 and calls == [720, 'closed']


def test_main_demonstrations_require_completed_curation_and_valid_provenance(tmp_path):
    from baseline.demo_source import snapshot_curated_source
    p = Protocol(protocol_file(tmp_path))
    ticket = tmp_path/'tickets'/'ticket-a'
    ticket.mkdir(parents=True)
    curation = ticket/'curation.json'
    write_json(curation, {'needs_more_demos':True,'export_root':'unused'})
    assert snapshot_curated_source('task-0',p,ticket.parent,tmp_path/'copies') is None
    assert not (tmp_path/'copies').exists()
    write_json(ticket/'ticket.json', {'suite':'s','task_id':'t','perturbation_variant':'v'})
    write_json(curation, {'needs_more_demos':False,'export_root':'unused','curation_sha256':'invalid'})
    with pytest.raises(ValueError, match='provenance has changed'):
        snapshot_curated_source('s::t::v',p,ticket.parent,tmp_path/'copies')


def test_pro_language_is_preserved_when_resource_generation_is_disabled():
    from baseline.environment import use_perturbed_instruction
    env = SimpleNamespace(task_description='original instruction', read_language_from_bddl=False,
                          bddl_file_name='existing-pro.bddl', _extract_language_from_bddl=lambda p:'perturbed instruction')
    adapter = SimpleNamespace(_env=[env])
    use_perturbed_instruction(adapter, {'perturbation_variant':'use_language'})
    assert env.task_description=='perturbed instruction' and env.read_language_from_bddl
    env._extract_language_from_bddl=lambda p:None
    with pytest.raises(ValueError, match='no BDDL instruction'):
        use_perturbed_instruction(adapter, {'perturbation_variant':'use_task'})
    use_perturbed_instruction(adapter, {'perturbation_variant':'use_object'})


@pytest.mark.parametrize('success_at,expected_steps,reason',[(None,705,'simulator_horizon'),(42,27,'success')])
def test_masked_libero_timeout_stops_without_an_extra_action(monkeypatch,success_at,expected_steps,reason):
    from baseline import rollout
    sim=SimpleNamespace(done=False,timestep=15,horizon=720)
    calls=[]
    def step(action):
        assert not sim.done, 'an action was sent after the simulator horizon'
        sim.timestep+=1
        sim.done=sim.timestep>=sim.horizon
        success=sim.timestep==success_at
        calls.append(sim.timestep)
        # Match LIBERO: its return value masks the internal done flag.
        return {},float(success),success,False,{'success':success}
    adapter=SimpleNamespace(step=step,_get_current_robosuite_env=lambda:SimpleNamespace(env=sim),
                            get_policy_observation=lambda **kw:{},close=lambda:None)
    monkeypatch.setattr(rollout,'make_environment',lambda cfg,ctx:adapter)
    monkeypatch.setattr(rollout,'reset_environment',lambda a,c:{})
    runtime=SimpleNamespace(policy=SimpleNamespace(reset=lambda:None),preprocess=lambda x:x,embed=lambda x:x,
                            prefix=lambda x:x,latent=lambda x:torch.zeros(1,3),sample=lambda x:torch.zeros(1,50,7),physical=lambda x:x)
    summary,records=rollout.episode(runtime,load_config(),{'seed':1},record=True)
    assert len(calls)==summary['steps']==expected_steps
    assert summary['termination_reason']==reason
    assert records[-1]['terminal'] and records[-1]['bootstrap_discount']==0
    assert records[-1]['steps']==expected_steps%10


def test_collection_continuation_reuses_only_verified_prefix(tmp_path,monkeypatch):
    from baseline import rollout
    from baseline.io import save_tensors,digest,read_json
    cfg=load_config(overrides={'method':'rl2_vla'})
    runtime=SimpleNamespace(identity={'sha256':'v44'})
    protocol=SimpleNamespace(digest='protocol')
    before={'task_key':'a','init_state_id':1,'seed':10,'policy_seed':20}
    after={**before,'seed':11,'policy_seed':21}
    monkeypatch.setattr(rollout,'collection_plan',lambda *a:[('train',before),('train',after)])
    source=tmp_path/'previous';source.mkdir()
    write_json(source/'config.json',cfg);write_json(source/'base_identity.json',runtime.identity)
    path=source/'episode.pt'
    save_tensors(path,{'summary':{'context':before,'success':True,'steps':4},'records':[{'latent':torch.ones(3)}]})
    entry={'path':str(path),'sha256':digest(path),'role':'train','task_key':'a','init_state_id':1,'seed':10,'success':True}
    write_json(source/'rollouts.json',{'base':runtime.identity,'protocol_sha256':'protocol','entries':[entry]})
    calls=[]
    def run(runtime,cfg,ctx,**kw):
        calls.append(ctx)
        return {'context':ctx,'success':False,'steps':5,'termination_reason':'simulator_horizon'},[{'latent':torch.zeros(3)}]
    monkeypatch.setattr(rollout,'episode',run)
    output=tmp_path/'resumed';output.mkdir()
    rollout.collect_rollouts(runtime,cfg,protocol,output,continue_from=source)
    assert calls==[after]
    assert read_json(output/'rollouts.json')['entries'][0]==entry
    assert digest(path)==entry['sha256']
    save_tensors(path,{'tampered':True})
    bad=tmp_path/'bad';bad.mkdir()
    with pytest.raises(ValueError,match='changed source episode'):
        rollout.collect_rollouts(runtime,cfg,protocol,bad,continue_from=source)


def test_only_complete_zero_update_grpo_groups_can_be_reused(tmp_path):
    from baseline.continuation import no_update_prefix,jsonl
    from baseline.experiment import task_order,training_contexts
    from baseline.io import append_json
    cfg=load_config(overrides={'method':'continual_vla_rl'})
    p=Protocol(protocol_file(tmp_path));runtime=SimpleNamespace(identity={'sha256':'v44'})
    key=task_order(cfg,p)[0];contexts=training_contexts(cfg,p,[key])
    source=tmp_path/'previous';source.mkdir()
    write_json(source/'config.json',cfg);write_json(source/'base_identity.json',runtime.identity)
    for group,count in ((1,8),(2,2)):
        base=contexts[group-1]
        for member in range(count):
            ctx={**base,'policy_seed':base['seed']+(group-1)*1009+member}
            append_json(source/'rollouts.jsonl',{'stage':0,'group':group,'member':member,'context':ctx,'success':True,'steps':10})
    append_json(source/'training.jsonl',{'stage':0,'group':1,'returns':[1.]*8,'informative':False,'updates':0,'environment_steps':80})
    output=tmp_path/'resumed';output.mkdir()
    assert no_update_prefix(source,runtime,cfg,p,output)==(1,100)
    assert len(jsonl(output/'rollouts.jsonl'))==8 and len(jsonl(source/'rollouts.jsonl'))==10
    append_json(source/'training.jsonl',{'phase':'grpo_update','step':1})
    with pytest.raises(ValueError,match='optimized weights'):
        no_update_prefix(source,runtime,cfg,p,output)
