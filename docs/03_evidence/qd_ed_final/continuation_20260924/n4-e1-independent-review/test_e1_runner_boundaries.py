"""Independent E1 metadata redteam. Synthetic temporary files only, no entrypoints."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
from contextlib import nullcontext
import pytest

J=Path("/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-n4-e1-runner-20260924")
PINNED={
 "scripts/qd_ed_n4e1_plan.py":"649449da2be43661080ce39f04f37fb5fd06e12360020937aca02da6d782f1cb",
 "scripts/qd_ed_n4e1_supervise.py":"6db2641a51e093d9c6b07afbbfed847256be8d22d55d8a2d5d5aa30f942ad41a",
 "scripts/qd_ed_n4e1_report.py":"69899bc1869d48c186a906a60d6d2d3d65269016d72c6914d60e4c3f19cc98ac",
 "scripts/qd_ed_final_runner.py":"fc1a7cdda18af2d013ea90cab581ddf89c7088fc1c22fe5e5139995ffce0c6ed",
 "scripts/qd_ed_available_gpu_queue.py":"0523d0a9020c27ca5e0f0c7e8209711d9edd349b458da3012c589c18d7f64cc2",
 "tests/test_qd_ed_n4e1.py":"9ff2ccecede9d2e61aa07456385ec5c19add7b7c631960c1841469426168c6c8"}
for rel,digest in PINNED.items():
 assert hashlib.sha256((J/rel).read_bytes()).hexdigest()==digest
sys.path[:0]=[str(J),str(J/"scripts"),str(J/"tests")]
import test_qd_ed_n4e1 as a
case=a.case
old_fixture=a.old_fixture
r,n,d=a.r,a.n,a.d

def release(case, keys, stage="first3"):
 root,p,_,rt,_,_,_,ref,_,_=case
 pr=ref("independent-plan",p)
 value={"schema":"qd-ed-n4e1-execution-release-v1","status":"authorized","cohort_id":n.COHORT,
 "plan":pr,"frozen_identity":n.binding(p,rt),"source_commit":p["source_commit"],
 "source_files_sha256":n.source_identity(p),"candidate_profiles":p["candidate_profiles"],
 "resource_authority":p["n4e1_cohort"]["resource_authority"],"limits":n.LIMITS,
 "budget_allocation":n.BUDGET_ALLOCATION,"phase_authorization":p["phase_authorization"],
 "physical_gpu":3,"max_owned_GPU_workers":1,"gpu_mapping":rt["gpu_mapping"],"episode_keys":keys,
 "stage":stage,"checkpoint_release":p["n4e1_cohort"].get("checkpoint_release") if stage=="remaining9" else None}
 return pr,ref("independent-release",value),value

def test_90_and_180_cannot_be_mixed_or_laddered(case):
 root,p,m,rt,seeds,*_=case
 old=case[-1]
 assert r.stage_overrides(old)["perception.gemini.timeout_seconds"]==90
 assert r.stage_overrides(rt)["perception.gemini.timeout_seconds"]==180
 for seconds in [91,179,181,360]:
  bad=copy.deepcopy(rt);bad["frozen_stage_provider"]["timeout_seconds"]=seconds
  with pytest.raises(r.GateError):r.stage_overrides(bad)
 bad=copy.deepcopy(p);bad["n4_cohort"]={}
 with pytest.raises(r.GateError,match="another cohort"):n.validate_contract(bad,m,rt,seeds,root,r)
 with pytest.raises(r.GateError):n.validate_contract(p,m,old,seeds,root,r)

@pytest.mark.parametrize("defect",["policy","input","source_whitelist"])
def test_runtime_and_source_mapping_exact_not_transport_blanket(case,defect):
 root,p,m,rt,seeds,*_=case
 if defect=="policy":rt["frozen_stage_provider"]["model"]="another-model"
 elif defect=="input":rt["environment"]["OMP_NUM_THREADS"]="1"
 else:p["n4e1_cohort"]["source_mapping"]["allowed_changed_paths"].append("main.py")
 with pytest.raises(r.GateError):n.validate_contract(p,m,rt,seeds,root,r)

@pytest.mark.parametrize("linktype",["symlink","hardlink"])
def test_private_resource_files_cannot_rejoin_another_owner(case,tmp_path,linktype):
 root,p,_,rt,*_=case
 path=root/"data/qd-ed-runner.lock"
 path.unlink()
 other=tmp_path/"other-owner-lock";other.touch()
 if linktype=="symlink":path.symlink_to(other)
 else:os.link(other,path)
 with pytest.raises(r.GateError,match="local regular"):n.resource_authority(p,rt,root,r)
 assert other.read_bytes()==b""

def test_release_epoch_and_scope_bind_plan_keys_condition(case):
 root,p,_,rt,_,_,_,ref,_,_=case
 keys=[x["episode_key"] for x in p["episodes"][:3]]
 pr,rr,value=release(case,keys)
 n.execution_release(rr,pr["path"],p,rt,keys,root,r)
 fourth=[p["episodes"][3]["episode_key"]]
 value["episode_keys"]=fourth
 with pytest.raises(r.GateError,match="phase/key"):n.execution_release(ref("wrong-phase",value),pr["path"],p,rt,fourth,root,r)
 value["stage"]="remaining9"
 with pytest.raises(r.GateError,match="checkpoint"):n.execution_release(ref("no-checkpoint",value),pr["path"],p,rt,fourth,root,r)
 Path(pr["path"]).write_text(json.dumps({**p,"frozen":False}))
 with pytest.raises(r.GateError,match="identity"):n.execution_release(rr,pr["path"],p,rt,keys,root,r)

def test_full1840_includes_new_health_and_preserves_24_reserved_hours(case,monkeypatch):
 root,p,_,rt,_,resources,state,*_=case
 snap={"dispatched":80,"by_bucket":{"baseline":16,"development":58,"recovery":6,"validation":0,"formal":0},
       "gpu_hours_consumed":24-1840/3600,"gpu_hours_by_bucket":dict.fromkeys(n.ORIGINAL_CAPS,0.)}
 monkeypatch.setattr(r,"budget_snapshot",lambda *args:snap)
 n.protected_budget(state,[],resources,p["episodes"][0],1800,r,plan=p)
 snap["gpu_hours_consumed"]+=1/3600
 with pytest.raises(r.GateError,match="protected 24"):n.protected_budget(state,[],resources,p["episodes"][0],1800,r,plan=p)
 p["n4e1_cohort"]["health_resources"].append({"resource_id":"new-health","scope":"new_n4e1"})
 resources.append({"resource_id":"new-health","event":"completed","gpu_process_wall_seconds":8.5*3600-1840+1})
 with pytest.raises(r.GateError,match="8.5-hour"):n.admission(p,rt,p["episodes"][0],[],resources,root,r)

def test_direct_entry_cannot_reach_hardware_or_ledger(case,monkeypatch):
 root,p,m,rt,*_=case
 monkeypatch.setattr(r,"validate_plan",lambda *args,**kw:(p,m,rt))
 monkeypatch.setattr(r,"locked",lambda *args,**kw:nullcontext())
 monkeypatch.setattr(r,"gpu_admission",lambda **kw:pytest.fail("hardware reached"))
 monkeypatch.setattr(r,"append_event",lambda *args,**kw:pytest.fail("ledger reached"))
 with pytest.raises(r.GateError,match="dedicated"):
  r.run_plan("synthetic",split="dev",iteration=n.COHORT,root=root)

def test_missing_usage_is_nonretryable_even_with_transport_label(case):
 root,p,_,rt,_,resources,_,_,event,_=case
 row=p["episodes"][0];ev=event(row,"bad",False,n.TRANSPORT_GATE);f=ev[-1]
 f.update(compute_outcome="completed",stage_backend="codex_cli",provider_failed_calls=1,stage_failed_queries=1,
          required_cost_telemetry_complete=False,provider_token_usage_complete=False,provider_input_tokens=99)
 assert n.transport_recovery_eligibility(r.GateError(n.TRANSPORT_GATE),f,p,row,rt,r) is None
 assert not n.recoverable(f,n.binding(p,rt))
 retry={**row,"episode_key":"retry","retry_of":"bad","budget_bucket":"recovery","n4e1_recovery_contract":n.binding(p,rt)}
 with pytest.raises(r.GateError):n.check_retry(ev,retry,r)
 with pytest.raises(r.GateError,match="prior valid"):n.admission(p,rt,p["episodes"][1],ev,resources,root,r)
 cost=d.cost_observation([f,{"provider_input_tokens":11,"provider_token_usage_complete":True}],"provider_input_tokens")
 assert cost["observed_subtotal"]==110 and cost["complete_total"] is None

@pytest.mark.parametrize("complete_rows",[3,11])
def test_partial_good_results_are_never_full_dev_promotion(case,complete_rows):
 _,p,_,rt,*_=case
 attempts=[a.public_attempt(p,rt,row,str(i),success=True) for i,row in enumerate(p["episodes"][:complete_rows])]
 result=d.summarize(p,attempts)
 assert result["matrix"]=="incomplete" and result["protocol_numeric_dev_criterion"] is None
 assert result["protocol_execution_activity_criterion"] is None and result["phase_authorized"] is False

def test_old_cohort_terminal_cannot_be_pooled_and_valid_failures_keep_denominator(case):
 _,p,_,rt,*_=case
 attempts=[a.public_attempt(p,rt,row,str(i),success=False) for i,row in enumerate(p["episodes"])]
 result=d.summarize(p,attempts)
 assert result["matrix"]=="complete_valid_12" and result["protocol_numeric_dev_criterion"] is False
 assert all(v["complete_valid"]==4 and v["failures_observed"]==4 and v["success_rate"]==0 for v in result["profiles"].values())
 terminal=copy.deepcopy(attempts[0]["terminal"]);terminal["identity"]["iteration"]=a.old.COHORT
 with pytest.raises(ValueError,match="identity"):d.validate_terminal(terminal,p,"base")

