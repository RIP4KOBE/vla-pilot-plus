from pathlib import Path
import json,hashlib,datetime,collections,importlib.util
art=Path('artifacts/stage_closed_loop_20260929'); f=art/'runs/codex_fused_carry_v16_historical_initialization_online_full10'
base=art/'runs/codex_partial_visibility_v14_historical_initialization_online_full10';out=f/'output'
def rows(p):
 if not p.exists(): return []
 lines=p.read_text().splitlines(); result=[]
 for i,l in enumerate(lines):
  try: result.append(json.loads(l))
  except json.JSONDecodeError:
   if i != len(lines)-1: raise
 return result
events=rows(out/'eds_eval/stage_events.jsonl'); actions=rows(out/'eds_eval/safety_events.jsonl')
reference=rows(base/'output/eds_eval/safety_events.jsonl')
mapping={(r['episode'],r['global_step']):r for r in reference}; differences=[]
for r in actions:
 b=mapping.get((r['episode'],r['global_step']))
 if b is not None and b['raw_action']!=r['raw_action']: differences.append({'task':r['task_id'],'step':r['global_step']})
calls=[]
for p in sorted(out.rglob('response.json')):
 d=json.loads(p.read_text()); t=d.get('transport',{}); c=d.get('counters',{})
 calls.append({'path':str(p.relative_to(f)),'ok':d.get('ok'),'model':t.get('model'),'effort':t.get('reasoning_effort'),'latency_s':c.get('call_latency_s'),'returncode':t.get('process_returncode'),'completed_turns':t.get('completed_turns'),'auth_mode':d.get('auth_mode'),'backend':d.get('backend')})
manifest=json.loads((f/'manifest.json').read_text()); frozen=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in manifest['source_sha256'].items())
spec=importlib.util.spec_from_file_location('v16_audit',f/'source/core/stage_fused_carry_hold.py')
if not Path(spec.origin).exists(): spec=importlib.util.spec_from_file_location('v16_audit',Path('core/stage_fused_carry_hold.py'))
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
summary={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'partial live prefix, not completed cohort audit','run':f.name,'progress':json.loads((out/'status.json').read_text()),'source_hashes_match_frozen':frozen,'stage_events':len(events),'stage_queries':sum(r.get('query_status')=='ok' for r in events),'query_error_events':sum(r.get('error') is not None for r in events),'completed_cli_calls':len(calls),'cli_failed':sum(not r['ok'] for r in calls),'all_call_provider_expected':all(r['backend']=='codex_cli' and r['auth_mode']=='chatgpt' and r['model']=='gpt-6-astra' and r['effort']=='low' for r in calls),'native_actions_recorded':len(actions),'action_overrides':sum(bool(r.get('override')) for r in actions),'executed_action_mismatches':sum(r.get('raw_action')!=r.get('executed_action') for r in actions),'first_action_difference_vs_v14':differences[0] if differences else None,'all_recorded_actions_equal_v14':bool(actions) and not differences,'fused_hold_establishments':[{'task':r['task_id'],'step':r['global_step'],'observation':r.get('observation')} for r in events if r.get('fused_hold_established')],'fusion_prefix_audit':mod.audit_checks(events),'latest_stage':{k:events[-1].get(k) for k in ['task_id','global_step','stage_after','guidance_after','contact_phase','query_status','fused_hold_established','completion_confirmed']} if events else None,'goal_complete':False}
per_task=[]
for task in sorted({r['task_id'] for r in actions}):
 aa=[r for r in actions if r['task_id']==task];ee=[r for r in events if r['task_id']==task];dd=[r for r in differences if r['task']==task]
 per_task.append({'task_id':task,'actions':len(aa),'last_action_step':aa[-1]['global_step'],'stage_queries':sum(r.get('query_status')=='ok' for r in ee),'first_stage2_step':next((r['global_step'] for r in ee if r['stage_after']==2),None),'stage2_chunks':sum(r['stage_after']==2 for r in ee),'guided_chunks':sum(bool(r['guidance_after']) for r in ee),'fused_hold_establishment_steps':[r['global_step'] for r in ee if r.get('fused_hold_established')],'first_action_difference_vs_v14':dd[0]['step'] if dd else None,'all_recorded_actions_equal_v14':not dd,'video_files':[p.name for p in (out/f'episode_{task+1}').glob('*agentview.mp4')]})
summary['per_task']=per_task
tmp=f/'live-prefix-review.json.tmp';tmp.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');tmp.replace(f/'live-prefix-review.json')
print(json.dumps(summary,ensure_ascii=False))

