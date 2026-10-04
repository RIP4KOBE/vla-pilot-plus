"""Actual RDT/Main method chains with controlled CPU services; no real environment."""
import copy
import inspect
from collections import Counter
import json
import ast
from pathlib import Path
from types import MethodType, SimpleNamespace
import pytest
import torch
import numpy as np
from test_rdt_steer import _patch_core_imports, stub_adapter, mock_batch, _StubRDTModel
from test_n30_executed_progress import setup_policy, q0, runtime_cfg, FakeRecorder, eq

ROOT = Path(__file__).resolve().parents[1]
MODE = "capture_dwell_proposal_v1"


def config():
    return json.loads((ROOT/"configs/qd_ed_final/candidate_n31.json").read_text())["profile"]


def packet(target=0., missing=None):
    p = {"episode": 0, "observed_eef": torch.zeros(3, dtype=torch.float64),
         "keypoints": torch.tensor([[target, 0., 0.]], dtype=torch.float64),
         "hand_quaternion_xyzw": torch.tensor([0., 0., 0., 1.], dtype=torch.float64),
         "gripper_qpos": torch.tensor([.02, -.02], dtype=torch.float64),
         "tracker": {"instance_id": 7, "generation": 1, "targets": {"0": {"valid": True, "status": "tracked"}}}}
    if missing:
        p[missing] = None
    return p


def project_adapter(adapter, monkeypatch):
    # Use the real adapter projection method AST, substituting only the pose service.
    tree = ast.parse((ROOT/"core/env_adapters/libero_adapter.py").read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "LiberoAdapter")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "delta_actions_to_ee_trajectory")
    ns = {"torch": torch, "np": np, "Union": __import__("typing").Union}
    exec(compile(ast.Module(body=[method], type_ignores=[]), "<real-libero-projection>", "exec"), ns)
    state = {"origins": 0}
    def pose():
        state["origins"] += 1
        return SimpleNamespace(position=np.zeros(3, dtype=np.float64))
    monkeypatch.setattr(adapter, "get_ee_pose_world", pose, raising=False)
    monkeypatch.setattr(adapter, "delta_actions_to_ee_trajectory", MethodType(ns[method.name], adapter))
    return state


def make(arm, adapter, monkeypatch, dtype, *, observer=True, old=False):
    import core.rdt_policy_steer as module
    p = module.RDTSteer(rdt_model=_StubRDTModel(), num_inference_steps=5)
    provider = setup_policy(p, adapter, monkeypatch, dtype)
    if old:
        pinned = json.loads((ROOT/"tests/n31_original_methods.json").read_text())
        for name, source in pinned["policy"].items():
            ns = dict(vars(module)); exec(compile(source, "<pinned6292>", "exec"), ns)
            monkeypatch.setattr(p, name, MethodType(ns[name], p))
    counts = project_adapter(adapter, monkeypatch)
    counts["projection_calls"]=[]
    projection=p._rdt_sample_to_trajectory_3d
    def counted_projection(samples, **kw):
        frame=inspect.currentframe().f_back
        stack=[]
        while frame is not None and len(stack)<3:
            stack.append({"function":frame.f_code.co_name,"line":frame.f_lineno,
                          "file":frame.f_code.co_filename})
            frame=frame.f_back
        before=counts["origins"]
        result=projection(samples,**kw)
        counts["projection_calls"].append({"shape":list(samples.shape),"stack":stack,
            "origin_reads":counts["origins"]-before})
        return result
    monkeypatch.setattr(p,"_rdt_sample_to_trajectory_3d",counted_projection)
    rec = FakeRecorder() if observer else None
    p._decision_evidence = rec
    # Still run the entire ordinary initial sampler and RNG/model/RBF schedule.
    ordinary = p._eds_initial_population
    initial = []
    def controlled(*a, **k):
        x = ordinary(*a, **k)
        x = x.clone()
        x[0] = 0; x[0, :, 10] = -1
        x[0, :8, 39] = .2
        p._last_eds_initial_sampler_trace_stages=[(name,x.detach() if name=="initial_final" else values)
            for name,values in p._last_eds_initial_sampler_trace_stages]
        initial.append(x.detach().clone())
        return x
    monkeypatch.setattr(p, "_eds_initial_population", controlled)
    conf = q0() if arm == "off" else config()
    return p, provider, conf, rec, counts, initial


def execute(p, provider, config, batch, ctx):
    torch.manual_seed(310)
    actions = p.select_action(batch, generate_new_chunk=True, use_guidance=True,
        keypoints=np.array([[.01, 0., 0.]], dtype=np.float64), guidance_fns=[provider],
        guidance_type="eds", eds_config=config, global_step=0, current_stage=1,
        **({"capture_dwell_context": ctx} if ctx is not ... else {}))
    return actions, p.get_episode_compute_counters(), torch.random.get_rng_state()


@pytest.mark.parametrize("dtype", [torch.float32, torch.bfloat16])
@pytest.mark.parametrize("pretest", [False, True])
def test_full10_active_and_nohit_cost_rng_trace(stub_adapter, mock_batch, monkeypatch, tmp_path, dtype, pretest):
    from core.qd_capture_dwell import CaptureDwellDecision
    original_apply=CaptureDwellDecision.apply
    boundaries=[]
    def audited_apply(self,population,evidence):
        before=population.detach().clone(); rng=torch.random.get_rng_state()
        result=original_apply(self,population,evidence)
        assert eq(before[:15],result[:15]) and eq(before,population)
        assert eq(rng,torch.random.get_rng_state())
        boundaries.append((before,result.detach().clone()))
        return result
    monkeypatch.setattr(CaptureDwellDecision,"apply",audited_apply)
    outputs = {}
    for arm in ("old", "off", "nohit", "active"):
        p, provider, conf, rec, counts, initial = make("off" if arm in {"old","off"} else "on",
            stub_adapter, monkeypatch, dtype, old=arm=="old")
        if pretest: conf = runtime_cfg(conf)
        ctx = packet(.01)
        if arm == "nohit": ctx["gripper_qpos"] = torch.tensor([.04, .03], dtype=torch.float64)
        out = execute(p, provider, conf, mock_batch, ... if arm=="old" else ctx)
        outputs[arm] = (*out, counts["origins"], initial[0])
        (tmp_path/(arm+"-projection.json")).write_text(json.dumps(counts,indent=2))
        m = p.get_last_eds_metrics()
        assert m["score_call_count"] == 11 and m["search_evaluation_count"] == 176
        assert out[1]["model_forward_calls"] == 21 and out[1]["model_batch_rows"] == 336
        assert out[1]["rbf_gradient_calls"] == 19
        assert out[1]["reward_scoring_batches"] == (16 if pretest else 11)
        assert out[1]["reward_evaluations"] == (256 if pretest else 176)
        events = rec.events
        if arm in {"old","off"}:
            assert "capture_dwell_proposal" not in m
            continue
        assert m["capture_dwell_proposal"]["canonical_occurrences"] == 176
        opportunities = [x for x in events if x["event"]=="n31_capture_dwell_opportunity"]
        canonical = [x for x in events if x["event"]=="canonical_candidate_batch"]
        assert len(opportunities)==10 and len(canonical)==11
        assert p._capture_dwell is None
        for i, event in enumerate(opportunities):
            scored = event["actual_scored_population"]
            assert eq(scored, canonical[i+1]["candidates"])
            assert event["source"]["projection"].shape == (8,3)
            if arm=="active":
                assert event["candidate"] is not None
                assert eq(scored[15], event["candidate"])
                src=event["source"]["plan"]; j=event["arrival_index"]
                assert eq(scored[15,8:],src[8:]) and eq(scored[15,j,39:45],src[j,39:45])
            else:
                assert event["candidate"] is None and event["reason"]=="no_projected_entry"
                assert eq(scored[15],event["original_post_rollout_slot15"])
        assert m["capture_dwell_proposal"]["changed"] == (10 if arm=="active" else 0)
        if pretest:
            trace=p.get_last_eds_mechanism_trace()
            final=next(x for x in trace.stages if x.stage=="rollout_final")
            assert eq(final.costs, -canonical[1]["effective_quality"])
        if arm=="active":
            # Constructed dwell is worse for the original weighted approach score;
            # the unchanged archive is allowed to retain/select another candidate.
            selected=next(x for x in events if x["event"]=="final_selection")["selected_latent"]
            assert not any(eq(selected[0],e["candidate"]) for e in opportunities)
    for arm in ("off","nohit"):
        assert eq(outputs["old"][0],outputs[arm][0])
    for arm in ("off","nohit","active"):
        assert outputs[arm][1] == outputs["old"][1]
        assert eq(outputs[arm][2],outputs["old"][2])
        if arm != "active":
            assert outputs[arm][3] == outputs["old"][3]
        # Active proposals can change final archive cardinality: downstream
        # pre-existing archive diagnostics project that many rows, not always16.
        assert eq(outputs[arm][4],outputs["old"][4])
    call_records={arm:json.loads((tmp_path/(arm+"-projection.json")).read_text()) for arm in outputs}
    def profile(data):
        return Counter((tuple(x["function"] for x in v["stack"]),tuple(v["shape"]))
                       for v in data["projection_calls"])
    old_counts=profile(call_records["old"])
    for arm in ("off","nohit","active"):
        current=profile(call_records[arm]);delta={str(k):current[k]-old_counts[k]
            for k in current.keys()|old_counts.keys() if current[k]!=old_counts[k]}
        if arm != "active":assert not delta
        else:
            for k in current.keys()|old_counts.keys():
                if current[k]!=old_counts[k]:
                    assert k[0]==("_eds_target_distance","_eds_guided_denoise_loop","_predict_guided")
                    assert k[1][1:]==(64,128)
        (tmp_path/(arm+"-projection-delta.json")).write_text(json.dumps(delta,indent=2))


@pytest.mark.parametrize("observer", [False, True])
def test_observer_cannot_change_proposal(stub_adapter,mock_batch,monkeypatch,observer):
    out=[]
    for enabled in (False,observer):
        p,provider,conf,rec,counts,_=make("on",stub_adapter,monkeypatch,torch.float32,observer=enabled)
        result=execute(p,provider,runtime_cfg(conf),mock_batch,packet(.01))
        out.append((result,p.get_last_eds_metrics()["capture_dwell_proposal"]))
    assert eq(out[0][0][0],out[1][0][0]) and eq(out[0][0][2],out[1][0][2])
    assert out[0][0][1]==out[1][0][1]
    assert out[0][1]["reasons"]==out[1][1]["reasons"]


@pytest.mark.parametrize("route", ["baseline","no_active_rbf","fallback"])
def test_actual_rollout_paths_insert_before_sole_score(stub_adapter,mock_batch,monkeypatch,route):
    results=[]
    for on in (False,True):
        p,provider,conf,rec,counts,_=make("on" if on else "off",stub_adapter,monkeypatch,torch.float32)
        if route=="baseline":
            # Exercise actual baseline method without weakening frozen Q0 config.
            base=p._eds_rollout_baseline_reference
            def baseline(**kw):
                kw.pop("iter_idx");return base(**kw)
            monkeypatch.setattr(p,"_eds_rollout_reference",baseline)
        if route=="no_active_rbf":
            monkeypatch.setattr(p,"_eds_should_apply_rollout_diversity",lambda *a:False)
        if route=="fallback":
            old=p._compute_eds_diversity_gradient
            inside = [False]
            rollout = p._eds_rollout_reference
            def fallback(*a, **kw):
                inside[0] = True
                try: return rollout(*a, **kw)
                finally: inside[0] = False
            def gradient(*a, **kw):
                grad, evidence = old(*a, **kw)
                return (None if inside[0] else grad), evidence
            monkeypatch.setattr(p,"_eds_rollout_reference",fallback)
            monkeypatch.setattr(p,"_compute_eds_diversity_gradient",gradient)
        result=execute(p,provider,conf,mock_batch,packet(.01))
        results.append(result)
        if on:
            events=[e for e in rec.events if e["event"]=="n31_capture_dwell_opportunity"]
            assert len(events)==10 and all(e["candidate"] is not None for e in events)
            assert p.get_last_eds_metrics()["capture_dwell_proposal"]["canonical_batches"]==11
    assert results[0][1]==results[1][1] and eq(results[0][2],results[1][2])


def cache_fixture(dtype=torch.float32, duplicate=False):
    from core.qd_capture_dwell import CaptureDwellDecision
    from core.qd_executed_quality import recognize_executed_prefix_provider
    from test_rdt_steer import _n2_fixture_provider
    from core.qd_ed import QDArchive
    provider=_n2_fixture_provider(index=0)
    points=torch.zeros((1,3),dtype=dtype)
    semantic,_=recognize_executed_prefix_provider([provider],points)
    mask=torch.zeros((1,1,128),dtype=dtype);mask[:,:,[10,39,40,41,42,43,44]]=1
    d=CaptureDwellDecision(semantic,packet(),points,episode=0,stage=1,step=0,action_mask=mask)
    plans=torch.zeros((16,64,128),dtype=dtype);plans[:,:,10]=-1
    if not duplicate:plans[:,8,39]=torch.arange(16).to(dtype)
    xyz=torch.zeros((16,9,3),dtype=dtype)
    qualities=-torch.arange(16,dtype=dtype) if not duplicate else torch.zeros(16,dtype=dtype)
    projection={"projected_xyz":xyz,"source_origins":[torch.zeros(3,dtype=torch.float64) for _ in range(16)]}
    d.set_scope("canonical_initial",-1,"initial_population");d.record_score(plans,projection,qualities,-qualities,None)
    from core.qd_ed import QDArchiveEntry,fingerprint_action
    best=QDArchiveEntry(action=plans[0].clone(),reward=0.,cost=-0.,descriptor_xy_m=torch.zeros(2),
        fingerprint=fingerprint_action(plans[0]),source_iter=-1,parent_cell_id=None,insert_sequence=0,raw_reward=0.)
    archive=SimpleNamespace(select_global_best=lambda:(0,best))
    return d,plans,projection,provider,points,archive


def test_cache_no_alias_auxiliary_bound_and_duplicate_provenance():
    d,p,projection,provider,points,archive=cache_fixture(duplicate=True)
    saved=d.entries[0]["plan"].clone();p.add_(2);projection["projected_xyz"].add_(3)
    assert eq(saved,d.entries[0]["plan"]) and not bool(d.entries[0]["projection"].any())
    d.set_scope("auxiliary_pretest",0,"trace")
    d.record_score(None,None,None,None,None);assert len(d.entries)==16
    d.prepare(archive,0,[provider],points,None)
    assert d.pending["association"]=="identical_content_multiple_occurrences" and len(d.pending["matching_occurrences"])==16
    d.pending=None;d.entries[1]["projection"][0,0]=1
    with pytest.raises(RuntimeError,match="contradictory duplicate"):d.prepare(archive,0,[provider],points,None)


@pytest.mark.parametrize("fault", ["target","provider","archive_cost","source_iter","dtype","origin","order","double_apply"])
def test_provenance_rejects_contradictions(fault):
    d,plans,projection,provider,points,archive=cache_fixture()
    if fault=="target":
        with pytest.raises(ValueError,match="target changed"):d.prepare(archive,0,[provider],points+1,None)
    elif fault=="provider":
        with pytest.raises(RuntimeError,match="provider occurrence"):d.prepare(archive,0,[],points,None)
    elif fault in {"archive_cost","source_iter"}:
        best=archive.select_global_best()[1]
        from dataclasses import replace
        bad=replace(best,**{"cost" if fault=="archive_cost" else "source_iter":999})
        archive.select_global_best=lambda:(0,bad)
        with pytest.raises(RuntimeError):d.prepare(archive,0,[provider],points,None)
    elif fault in {"dtype","origin","order"}:
        d.entries=[];d.batches=0
        if fault=="dtype":projection["projected_xyz"]=projection["projected_xyz"].to(torch.bfloat16)
        if fault=="origin":projection["source_origins"][0]+=1
        if fault=="order":d.set_scope("canonical_offspring",0,"rollout")
        with pytest.raises((ValueError,RuntimeError)):d.record_score(plans,projection,torch.zeros(16),torch.zeros(16),None)
    else:
        d.prepare(archive,0,[provider],points,None);d.apply(plans,None)
        with pytest.raises(RuntimeError,match="double insertion"):d.apply(plans,None)


@pytest.mark.parametrize("missing", ["tracker","hand_quaternion_xyzw","gripper_qpos","keypoints"])
def test_missing_observation_explicit_skip(stub_adapter,mock_batch,monkeypatch,missing):
    p,provider,conf,rec,counts,_=make("on",stub_adapter,monkeypatch,torch.float32)
    execute(p,provider,conf,mock_batch,packet(.01,missing))
    assert p.get_last_eds_metrics()["capture_dwell_proposal"]["changed"]==0


def test_packet_copy_native_hplus1_and_no_cross_decision(stub_adapter,mock_batch,monkeypatch):
    from core.qd_capture_dwell import CaptureDwellDecision
    d,plans,projection,provider,points,archive=cache_fixture()
    assert eq(d.entries[0]["projection"],projection["projected_xyz"][0,1:9])
    ctx=packet();ctx["gripper_qpos"]=ctx["gripper_qpos"][None]
    e=CaptureDwellDecision(d.semantic,ctx,points,episode=0,stage=1,step=8,action_mask=d.mask)
    assert ctx["gripper_qpos"].shape==(1,2) and e.packet["gripper_qpos"].shape==(2,)
    assert not e.entries
    p,provider,conf,rec,counts,_=make("on",stub_adapter,monkeypatch,torch.float32)
    p._capture_dwell=d
    p.reset_stage();assert p._capture_dwell is None
    p._capture_dwell=d;p.reset();assert p._capture_dwell is None


def test_profile_and_actual_hydra_compose(stub_adapter,monkeypatch):
    from hydra import compose,initialize_config_dir
    from omegaconf import OmegaConf
    p,_,conf,_,_,_=make("on",stub_adapter,monkeypatch,torch.float32)
    assert {k:v for k,v in conf.items() if k not in q0() or v!=q0()[k]}=={"capture_dwell_proposal_mode":MODE}
    resolved=p._resolve_eds_config_with_reference_defaults(conf);assert resolved.capture_dwell_proposal_mode==MODE
    with initialize_config_dir(config_dir=str(ROOT/"configs"),version_base=None):
        composed=compose(config_name="config",overrides=["main.eds_config.capture_dwell_proposal_mode="+MODE])
    assert composed.main.eds_config.capture_dwell_proposal_mode==MODE
    for change in ({"executed_progress_continuation_mode":"executed_progress_continuation_v1"},
                   {"qd_parent_survivor_count":1},{"qd_quality_mode":"actuator_clipped_v1"}):
        with pytest.raises(ValueError):p._resolve_eds_config_with_reference_defaults({**conf,**change})


@pytest.mark.parametrize("observer",[False,True])
def test_complete_main_raw_packet_no_new_observation(stub_adapter,monkeypatch,tmp_path,observer):
    from test_n30_initial_observation_repair import make_case,run
    case=make_case(stub_adapter,monkeypatch,tmp_path,mode="Q0",steps=16)
    app,p,rec,state=case
    app.config["eds_config"]=config()
    # Raw cached adapter fields carry native float64; preprocessor erases robot_state.
    def enrich(obs):
        obs["observation.robot_state"]["eef"]["quat"]=torch.tensor([[0.,0.,0.,1.]],dtype=torch.float64)
        obs["observation.robot_state"]["gripper"]={"qpos":torch.tensor([[.02,-.02]],dtype=torch.float64)}
        return obs
    enrich(stub_adapter._last_obs)
    old=stub_adapter.step
    def step(a):
        o,r,t,tr,i=old(a);enrich(o);return o,r,t,tr,i
    stub_adapter.step=step
    project_adapter(stub_adapter,monkeypatch)
    if not observer:
        app._enable_decision_evidence=lambda ep:None;p._decision_evidence=None;stub_adapter._decision_evidence=None
        rec.all_events=[];rec.finished=False
    out=run(case)
    assert out["cache_reads"]==1 and out["policy_reads"]==17 and out["steps"]==16
    assert out["tracker_reads"]==out["snapshots"]==2
    assert all("observation.robot_state" not in x for x in out["processed"])
    if observer:
        events=[e for e in out["events"] if e["event"]=="n31_observation_context"]
        assert len(events)==2
        assert all(e["values"]["packet"]["hand_quaternion_xyzw"].dtype==torch.float64 for e in events)
    assert not hasattr(p,"_executed_progress")
    assert out["compute"]["model_forward_calls"]==42 and out["compute"]["rbf_gradient_calls"]==38
    assert out["compute"]["reward_scoring_batches"]==32 and out["compute"]["reward_evaluations"]==512



@pytest.mark.parametrize("fault",["mask","episode","nonfinite","packet_shape","unrecognized","unrecognized_malformed"])
def test_context_contract_and_unrecognized_skip(fault):
    from core.qd_capture_dwell import CaptureDwellDecision
    d,plans,projection,provider,points,archive=cache_fixture()
    ctx=packet();mask=d.mask.clone();semantic=d.semantic
    if fault=="mask":mask[0,0,11]=1
    if fault=="episode":ctx["episode"]=1
    if fault=="nonfinite":ctx["gripper_qpos"][0]=float("nan")
    if fault=="packet_shape":ctx["hand_quaternion_xyzw"]=torch.zeros(3)
    if fault=="unrecognized_malformed":
        semantic=None;ctx["gripper_qpos"][0]=float("nan")
    if fault=="unrecognized":
        e=CaptureDwellDecision(None,ctx,points,episode=0,stage=1,step=0,action_mask=mask)
        e.set_scope("canonical_initial",-1,"initial_population")
        q=-torch.arange(16,dtype=plans.dtype);e.record_score(plans,projection,q,-q,None)
        e.prepare(archive,0,[provider],points,None)
        assert e.pending["candidate"] is None and e.pending["reason"]=="unrecognized_target"
    else:
        with pytest.raises(ValueError):
            CaptureDwellDecision(semantic,ctx,points,episode=0,stage=1,step=0,action_mask=mask)


@pytest.mark.parametrize("boundary",["empty_provider","no_keypoints","non_template"])
def test_real_unsupported_input_baseline_parity(stub_adapter,mock_batch,monkeypatch,tmp_path,boundary):
    outcomes=[]
    for arm in ("old","off","on"):
        p,provider,conf,rec,counts,_=make("on" if arm=="on" else "off",
            stub_adapter,monkeypatch,torch.float32,old=arm=="old")
        points=None if boundary=="no_keypoints" else np.array([[.01,0.,0.]],dtype=np.float64)
        def unsupported(points,trajectory):return -(trajectory**2).sum()
        providers=[] if boundary=="empty_provider" else [unsupported] if boundary=="non_template" else [provider]
        torch.manual_seed(310)
        try:
            value=p.select_action(mock_batch,generate_new_chunk=True,use_guidance=True,
                keypoints=points,guidance_fns=providers,guidance_type="eds",eds_config=conf,
                global_step=0,current_stage=1,**({"capture_dwell_context":packet(.01)} if arm!="old" else {}))
            status={"accepted":True}
        except Exception as exc:
            value=None;status={"accepted":False,"error":type(exc).__name__,"message":str(exc)}
        (tmp_path/(arm+"-boundary.json")).write_text(json.dumps(status,indent=2))
        print(boundary,arm,status)
        outcomes.append((status,value,p.get_episode_compute_counters(),torch.random.get_rng_state(),counts["origins"]))
        if arm=="on" and status["accepted"]:
            m=p.get_last_eds_metrics()["capture_dwell_proposal"]
            assert m["changed"]==0 and m["reasons"]==["unrecognized_target"]*10
    if boundary=="no_keypoints":
        assert all(not x[0]["accepted"] and x[0]["error"]=="ValueError" for x in outcomes)
        assert outcomes[0][0]["message"]==outcomes[1][0]["message"]=="QD descriptor requires keypoints"
    else:
        assert all(x[0]["accepted"] for x in outcomes)
        for x in outcomes[1:]:
            assert eq(x[1],outcomes[0][1]) and x[2]==outcomes[0][2]
            assert eq(x[3],outcomes[0][3]) and x[4]==outcomes[0][4]


@pytest.mark.parametrize("recognized",[False,True])
def test_missing_projection_is_not_generic_tolerance(recognized):
    d,plans,projection,provider,points,archive=cache_fixture()
    if not recognized:d.semantic=None;d.reason="unrecognized_target"
    d.entries=[];d.batches=0
    with pytest.raises(RuntimeError,match="missing canonical projection"):
        d.record_score(plans,{"capture_origin":True},torch.zeros(16),-torch.zeros(16),None)
