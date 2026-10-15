"""Root metadata-only verification of the completed metered CUDA proof."""
from pathlib import Path
import datetime,json,sys
V=Path(__file__).resolve().parent;ROOT=V.parents[1]/'study_worktree';sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n28_contract as c,qd_ed_n28_backend as b
source=json.loads((V/'source-manifest-execution-v1.json').read_text());runtime=c.runtime_ref()
proof=b.verify_proof(c.ref(c.BACKEND_PROOF),source,runtime,ROOT)
resources=r.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl');events=r.read_events(ROOT/'data/attempt-ledger.jsonl')
b.settled_proof(proof,resources,vars(r));snap=r.budget_snapshot(events,resources)
report=w.read_ref(proof['report']);process=w.read_ref(proof['process']);terminal=w.read_ref(proof['terminal'])
assert len(report['cases'])==24 and all(x['accepted'] for x in report['cases'])
assert report['model_calls']==report['api_calls']==report['simulation_steps']==report['episodes']==0
assert report['backend']['physical_gpu']==7 and report['backend']['physical_uuid']==c.GPU7_UUID
pid=Path('/proc')/str(process['pid']);same=False
if pid.exists():same=(pid/'stat').read_text().rsplit(')',1)[1].split()[19]==process['proc_start_ticks']
assert not same and snap['dispatched']==355 and snap['running']==snap['gpu_healthcheck_inflight']==0
old=w.read_ref(c.ref(V/'root-source-runtime-check-v1.json'))['budget_snapshot']
assert abs(snap['gpu_hours_consumed']-old['gpu_hours_consumed']-terminal['gpu_process_wall_seconds']/3600)<1e-8
assert snap['by_bucket']==old['by_bucket']
result={'schema':'n28-root-native-proof-review-v1','reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'decision':'ACCEPT_METERED_CUDA_PARENT_WRAPPER_PROOF','proof':c.ref(c.BACKEND_PROOF),'source_commit':source['commit'],
 'cases':24,'case_dtypes':['torch.float32','torch.bfloat16'],'gpu_uuid':c.GPU7_UUID,'worker_pid':process['pid'],'original_worker_exited':True,
 'gpu_process_wall_seconds':terminal['gpu_process_wall_seconds'],'budget_snapshot':snap,'episode_attempt_slots_used':0,
 'historical_proof_rerun':False,'native_cuda_replay_by_root':False,'root_tensor_payload_reads':0,
 'scope':'Synthetic parent mutation, independent exact native arithmetic, assignment/tail/RNG and observer binding. Does not prove real renoise entry or denoiser causal transfer or task efficacy.',
 'new_stage_api_calls':0,'dev_execution_authorized_by_this_review':False,'target_status':'TARGET_NOT_MET'}
w.atomic_json(V/'root-native-proof-review-v1.json',result)
print(json.dumps({'decision':result['decision'],'cases':24,'gpu_seconds':result['gpu_process_wall_seconds'],'dispatched':snap['dispatched'],'gpu_hours':snap['gpu_hours_consumed'],'worker_exited':True}))

