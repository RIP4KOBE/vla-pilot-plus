from pathlib import Path
import sys,json,copy,datetime
W=Path("/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z")/'study_worktree';R=W.parent;N=R/'variants/n23_actuator_clipped_quality'
sys.path.insert(0,str(W))
from scripts import qd_ed_final_runner as r
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n23_v2_contract as c
from scripts import qd_ed_n23_v2_prepare as prep
from scripts import qd_ed_n23_arithmetic_repair as repair
import torch
source=w.source_record(W,c.source_paths(vars(r)))
assert len(sys.argv)==2 and source['commit']==sys.argv[1]
changed=repair.source_delta(W)
old=json.loads((N/'backend-preflight-plan.uuid-native-repair.frozen.v2.json').read_text())['source']
checked=0
for entry in old['files']:
 if entry['path'] not in repair.ALLOWED_DELTA:
  assert w.sha(W/entry['path'])==entry['sha256'],entry['path']
  checked+=1
runtime=w.read_ref(c.ref(c.GPU7_RUNTIME));files_checked=[0]
bound=dict(vars(r))
def verify_files(records,**kwargs):
 files_checked[0]+=len(records)
 return r.verify_files(records,**kwargs)
bound['verify_files']=verify_files
c.validate_runtime(runtime,W,bound)
events=r.read_events(W/'data/attempt-ledger.jsonl')
repair.named_failures(events,vars(r));repair.first.no_dev(events)
assert {e['attempt_id'] for e in repair.first.backend_events(events)}==set(repair.PRIOR_ATTEMPTS+[repair.FAILED_ATTEMPT])
state=r.read_state(W/'research-state.yaml')
resources=r.read_events(W/'data/gpu-healthcheck-ledger.jsonl')
c.full_capacity(state,events,resources,vars(r),preflight=True)
snap=r.budget_snapshot(events,resources)
predecessor=c.predecessor_review()
draft=prep.build_plan(predecessor=predecessor)
manifest=r.read_json(draft['profiles_path']);original=copy.deepcopy(manifest)
for arm,ref in draft['candidate_profiles'].items():
 manifest['profiles'][arm]=r.expand_candidate(arm,w.read_ref(ref),manifest['profiles']['Q0'])
assert all(manifest['profiles'][k]==original['profiles'][k] for k in ('C0','Q0'))
assert manifest['profiles']['N23']['resolved_eds_config']=={**manifest['profiles']['N7']['resolved_eds_config'],'qd_quality_mode':'actuator_clipped_provider_v1'}
frozen=runtime['frozen_stage_provider']
assert frozen['backend']=='codex_cli' and frozen['auth_mode']=='chatgpt'
assert not {'api_key','base_url','credential_env_name','access_token'} & set(frozen)
public=r.codex_public_config(frozen)
assert public['config_overrides']['model_provider']=='openai'
assert {'OPENAI_API_KEY','OPENAI_BASE_URL','CODEX_API_KEY','CODEX_ACCESS_TOKEN'} <= set(public['removed_child_environment'])
commands=[]
for row in draft['episodes']:
 argv,output=r.build_command(draft,manifest,runtime,row,'cpu_review_uuid_repair__'+row['episode_key'])
 assert not output.exists()
 assert any(a.endswith('perception.gemini.backend=codex_cli') for a in argv)
 commands.append({'task_id':row['task_id'],'profile':row['profile'],'argv_sha256':w.canonical_sha(argv)})
assert len(commands)==40 and not torch.cuda.is_initialized()
report={'schema':'n23-root-arithmetic-repair-cpu-review-v3','recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'source':source,'original_source_commit':old['commit'],'allowed_changed_files':changed,'unchanged_original_source_files_verified':checked,
 'runtime':c.ref(c.GPU7_RUNTIME),'runtime_file_records_verified':files_checked[0],
 'failure_gate':'PASS','capacity_gate':'PASS','predecessor_review':predecessor,'budget_snapshot':snap,'commands':commands,
 'baseline_profiles_byte_identical':True,'sole_scientific_profile_delta':{'qd_quality_mode':'actuator_clipped_provider_v1'},
 'provider_backend':'codex_cli','auth_mode':'chatgpt','poe_api_disabled':True,'credentials_read_or_modified':False,
 'cuda_initialized':False,'gpu_dispatched':False,'reader_sha256':w.sha(__file__),
 'earlier_root_check_correction':'A preliminary inline review incorrectly required explicit null API-key/URL argv flags. The actual frozen managed-login contract instead forbids these keys entirely and strips child auth/provider overrides. Its assertion failed before any file/state write or GPU call; this check now verifies that existing contract without modifying it.'}
p=N/'root-arithmetic-repair-cpu-review-v3.json';assert not p.exists();w.atomic_json(p,report)
final={'schema':'n23-final-source-runtime-review-arithmetic-repair-v3','disposition':'accepted','source':source,'runtime':c.ref(c.GPU7_RUNTIME),
 'dev_protocol':c.ref(c.PROTOCOL),'backend_protocol':c.ref(c.BACKEND_PROTOCOL),'amendment':c.ref(c.BUDGET_AMENDMENT),
 'timeout_observability':c.ref(c.OBSERVABILITY),'exception':c.ref(repair.EXCEPTION),'failed_review':c.ref(repair.FAILURE_REVIEW),'prior_failure':c.ref(repair.prior.FAILURE_REVIEW),'audit_correction':repair.CORRECTION,'no_gpu_release':True}
assert not repair.FINAL_REVIEW.exists();w.atomic_json(repair.FINAL_REVIEW,final)
assert repair.final_review(source,c.ref(c.GPU7_RUNTIME))==c.ref(repair.FINAL_REVIEW)
print(json.dumps({'root_review':c.ref(p),'final_review':c.ref(repair.FINAL_REVIEW),'source_files':len(source['files']),
 'source_sha256':source['sha256'],'runtime_files':files_checked[0],'commands':len(commands),'capacity':'PASS','cuda_initialized':False}))

