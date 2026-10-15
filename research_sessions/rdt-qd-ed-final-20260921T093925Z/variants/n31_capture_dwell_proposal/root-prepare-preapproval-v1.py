from pathlib import Path
import os,sys,json,hashlib,datetime
P=Path(__file__).resolve().parent;W=P.parents[1]/'study_worktree'
os.environ['CUDA_VISIBLE_DEVICES']='';sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n31_contract as c,qd_ed_n31_bridge as b,qd_ed_n31_prepare as prepare
source=w.source_record(W,c.source_paths(vars(r)))
assert source==json.loads((P/'source-manifest-execution-v1.json').read_text())
runtime_ref=c.runtime_ref();runtime=w.read_ref(runtime_ref)
bridge=b.build(source,runtime_ref,W)
w.atomic_json(P/'source-equivalence-bridge-v1.json',bridge)
plan=prepare.build_plan(source=source,root=W)
assert plan['frozen'] is False and all(plan['n31_cohort'][k] is None for k in ('authority','final_review','budget_reuse'))
w.atomic_json(P/'plan.preview.owning.disabled.v1.json',plan)
provider=runtime['frozen_stage_provider']
assert provider['backend']=='codex_cli' and provider['auth_mode']=='chatgpt'
record={'schema':'n31-root-preapproval-preparation-v1','recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':source,'runtime':runtime_ref,'source_bridge':c.ref(P/'source-equivalence-bridge-v1.json'),'owning_preview':c.ref(P/'plan.preview.owning.disabled.v1.json'),'frozen':False,'gpu_authorized':False,'budget_adopted':False,'historical_tensor_replay':False,'runtime_provider_public':{k:provider.get(k) for k in ('backend','auth_mode','model','reasoning_effort','timeout_seconds','cli_path','cli_version','cli_sha256')},'next':'Bind actual approval, final review and authority; freeze unchanged full30 plan; fresh idle GPU/provider/data/locks admission before release.'}
w.atomic_json(P/'root-preapproval-preparation-v1.json',record)
print(json.dumps({k:v for k,v in record.items() if k not in ('source',)},indent=2))

