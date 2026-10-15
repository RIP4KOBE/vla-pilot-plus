"""Read-only attribution of recorded EDS task4 divergence; no execution/replay."""
from pathlib import Path
import ast,datetime,hashlib,json
ROOT=Path(__file__).resolve().parents[4]
BASE=ROOT/'.worktrees/exp/steering-integration'
RUNS={'current':BASE/'runs/eds-common-20261013','migration':BASE/'runs/eds-migration-20261013'}
EVAL={'current':'output/evaluation','migration':'output/eds_eval'}
TASK=4
OUTPUT=BASE/'checks/eds-common-task4-online-divergence.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canon(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def rows(p):
 result=[]
 for line in p.read_bytes().splitlines():
  try:result.append(json.loads(line))
  except json.JSONDecodeError:break
 return result
def selected(run,name):return [r for r in rows(run/name) if r.get('task_id',r.get('metadata',{}).get('task_id'))==TASK]
def capture(run,index):
 p=run/'output/captured_stage_inputs'/f'request_{index:04d}'
 m=json.loads((p/'metadata.json').read_text());reply=json.loads((p/'response.json').read_text())
 prompt=(p/'codex_prompt.txt').read_text()
 assert sha(p/'codex_prompt.txt')==m['prompt_sha256']
 assert sha(p/'image_01.png')==m['image_png_sha256'][0]
 return {'relative_path':str(p.relative_to(run)),'context':reply['context'],'prompt_sha256':sha(p/'codex_prompt.txt'),'image_png_sha256':sha(p/'image_01.png'),'response_sha256':sha(p/'response.json'),'raw_response':reply['raw_response'],'response_ok':reply['ok'],'text':prompt}
manifest={k:json.loads((r/'manifest.json').read_text()) for k,r in RUNS.items()}
assert manifest['current']['commit']=='33954ead452927fc3168efb610487a688f89169e'
for k,r in RUNS.items():
 assert all(sha(r/'source'/p)==h for p,h in manifest[k]['source_sha256'].items())
assert all(sha(ROOT/p)==h for p,h in manifest['current']['source_sha256'].items())
events={k:selected(r,EVAL[k]+'/stage_events.jsonl') for k,r in RUNS.items()}
by_step={k:{x['global_step']:x for x in v} for k,v in events.items()}
actions={k:[x for x in selected(r,EVAL[k]+'/safety_events.jsonl') if x.get('event')=='stage_grasp_guard_action'] for k,r in RUNS.items()}
for v in actions.values():assert [x['global_step'] for x in v]==list(range(720))
raw_diff=[i for i in range(720) if actions['current'][i]['raw_action']!=actions['migration'][i]['raw_action']]
exe_diff=[i for i in range(720) if actions['current'][i]['executed_action']!=actions['migration'][i]['executed_action']]
assert raw_diff==exe_diff==list(range(472,720))
queries={k:[x['global_step'] for x in v if x.get('query_status')=='ok'] for k,v in events.items()}
shared=sorted(set(queries['current'])&set(queries['migration']))
comparisons=[]
for step in shared:
 if step>472:continue
 pair={}
 for k,run in RUNS.items():
  e=by_step[k][step];ix=e['validation_attempts'][0]['capture_query_index'];c=capture(run,ix)
  assert c['context']['task_id']==TASK and c['context']['global_step']==step and c['raw_response']==e['raw_response']
  identity=e['identity_memory'];assert c['text'].count(identity)==1
  c['prompt_normalized_identity_sha256']=hashlib.sha256(c['text'].replace(identity,'<IDENTITY_MEMORY>').encode()).hexdigest()
  del c['text'];pair[k]=c
 comparisons.append({'global_step':step,'image_png_exact':pair['current']['image_png_sha256']==pair['migration']['image_png_sha256'],'prompt_exact':pair['current']['prompt_sha256']==pair['migration']['prompt_sha256'],'prompt_exact_except_identity':pair['current']['prompt_normalized_identity_sha256']==pair['migration']['prompt_normalized_identity_sha256'],'captures':pair})
identity={k:capture(r,128) for k,r in RUNS.items()}
for c in identity.values():assert c['text'].startswith('Identify only the instructed target object.');del c['text']
rng={k:selected(r,EVAL[k]+'/episode_rng_events.jsonl') for k,r in RUNS.items()}
rng_comp=[{'phase':phase,**{k:{field:next(x for x in v if x['metadata']['phase']==phase)[field] for field in ('sha256','state_signature')} for k,v in rng.items()}} for phase in ('prepare','rollout')]
source_checks=[]
for path,names in [('core/stage_evidence.py',('settings','decide','apply_guidance_gate','query_reason')),('core/stage_contact_handoff.py',('apply_handoff',))]:
 trees={k:{n.name:ast.dump(n,include_attributes=False) for n in ast.parse((r/'source'/path).read_text()).body if isinstance(n,ast.FunctionDef)} for k,r in RUNS.items()}
 source_checks.extend({'file':path,'function':name,'ast_exact':trees['current'][name]==trees['migration'][name]} for name in names)
keys=['global_step','stage_before','stage_after','guidance_before','guidance_after','query_status','trigger_reason','stage_decision_reason','contact_phase','contact_until','visual_hold','reward_reference_reset','guidance_gate_reason','control_observation','observation','reward_capability','physical_carry_evidence','robot_evidence']
focus={k:[{**{field:by_step[k][step].get(field) for field in keys},'marked_rgb_sha256':(by_step[k][step].get('current_target_marker') or {}).get('marked_rgb_sha256'),'capture_indices':[a['capture_query_index'] for a in by_step[k][step].get('validation_attempts',[])]} for step in (168,184,192,448,456,464,472,480)] for k in RUNS}
result={'schema':'eds_task_online_divergence_v1','generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'task_id':TASK,'seed':6,'runs':{k:{'path':str(r),'commit':manifest[k]['commit'],'manifest_sha256':sha(r/'manifest.json'),'task_stage_rows_sha256':canon(events[k]),'task_action_rows_sha256':canon(actions[k]),'terminal_videos':[p.name for p in (r/'output/episode_5').glob('*agentview.mp4')]} for k,r in RUNS.items()},'source_guard':{'current_frozen_files_checked':len(manifest['current']['source_sha256']),'current_and_archived_source_hashes_valid':True},'action_comparison':{'actions_each':720,'first_difference':472,'difference_steps':exe_diff,'exact_prefix_steps':472,'raw_and_executed_difference_sets_equal':True,'no_overrides_both':all(x['override'] is False and x['raw_action']==x['executed_action'] for v in actions.values() for x in v)},'observed_chain':['At step464 both runs queried on the same gripper-close trigger and byte-identical marked PNG; current fresh reply says grasp/support unknown, migration says held/unsupported.','Current stays Stage1/contact_grace until472; migration transitions Stage1→2 with visual_hold=true and reward-reference reset at464. Guidance remains OFF in both for464..471 and these actions stay exact.','At472 current contact_grace expires and Stage1 usable_reward enables EDS; migration remains Stage2 with constant_on_probes reward so guidance stays OFF. The first differing action is472.','Earlier schedule differences start at184 after step168 common not_held versus migration unknown replies. Queries are aligned again at368,384,400,416,448,464; all shared queried images before divergence are exact.'],'identity_capture':identity,'identity_prompt_and_image_exact':all(identity['current'][field]==identity['migration'][field] for field in ('prompt_sha256','image_png_sha256')),'identity_reply_exact':identity['current']['raw_response']==identity['migration']['raw_response'],'queries_before_or_at472':{k:[s for s in v if s<=472] for k,v in queries.items()},'shared_query_input_comparisons':comparisons,'records':focus,'initial_rng_proofs':rng_comp,'relevant_control_functions_static_ast':source_checks,'helper_sha256':sha(Path(__file__)),'limits':['Observed temporal/control sequence only; no counterfactual rerun or causal intervention was performed.','Observation prompts differ exactly in fresh identity_memory text. Identity wording and provider generation variability are not experimentally isolated.','Different fresh responses are recorded facts, not evidence that either semantic observation is ground truth.','No reward/model code, CPU/GPU episode, simulator or API was executed; no run files were modified.','This attribution does not replace the independent final cohort validity/integration acceptance gates.']}
assert not OUTPUT.exists()
assert all(sha(ROOT/p)==h for p,h in manifest['current']['source_sha256'].items())
OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'report':str(OUTPUT),'sha256':sha(OUTPUT),'shared_queries_compared':len(comparisons),'all_shared_images_exact':all(x['image_png_exact'] for x in comparisons),'all_shared_prompts_exact_except_identity':all(x['prompt_exact_except_identity'] for x in comparisons),'identity_prompt_image_exact':result['identity_prompt_and_image_exact'],'relevant_control_ast_exact':all(x['ast_exact'] for x in source_checks)}))
