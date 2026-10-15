from pathlib import Path
import json,hashlib,collections,datetime,os,sys
HERE=Path(__file__).resolve().parent;V=HERE.parent;R=V.parents[1];W=R/'study_worktree'
def sha(b):return hashlib.sha256(b).hexdigest()
def check(ok,msg):
 if not ok:raise ValueError(msg)
def file_ref(p,b=None):return {'path':str(p.resolve()),'sha256':sha(p.read_bytes() if b is None else b)}
scope=V/'planned-gripper-continuity-scope-v1.md';manifest=V/'planned-gripper-continuity-attempts-v1.json'
sb=scope.read_bytes();mb=manifest.read_bytes()
check(sha(sb)=='d99fa82a046dfbbea0f4849f86ab53ee603a132ab4df29626f7a3e22db88b97f','scope');check(sha(mb)=='cca36ad827d720aa7973e808d86db7fb00da961f44ba4203f57123626adc39f4','manifest')
m=json.loads(mb);items=[]
source_names=['main.py','core/decision_evidence.py','core/keypoint_tracker.py','core/rdt_libero_action_converter.py','core/rdt_policy_steer.py','scripts/audit_decision_evidence.py']
refs={n:file_ref(W/n) for n in source_names}
allowed={str(Path(a['terminal']['path']).resolve()) for a in m['attempts']}
for a in m['attempts']:
 out=Path(a['output_dir']);allowed.update(str((out/p).resolve()) for p in ['eds_eval/in-worker-audit-receipt.json','eds_eval/decision-evidence-audit.json','eds_eval/decision_evidence/episode_000/events.jsonl'])
roots=[str(R.resolve()),'/mnt/data/shared2/hynx/VLA-Pilot++'];blocked=[]
def guard(event,args):
 if event!='open':return
 path,mode,flags=args
 if isinstance(path,int):return
 p=str(Path(os.fsdecode(path)).resolve());write=bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
 if any(p.startswith(r+'/') for r in roots):
  if write and not p.startswith(str(HERE)+'/'):raise RuntimeError('write scope')
  if not write and p not in allowed and not p.startswith(str(HERE)+'/'):blocked.append(p);raise RuntimeError('read scope')
sys.addaudithook(guard)
for a in m['attempts']:
 out=Path(a['output_dir']);ed=out/'eds_eval';ep=ed/'decision_evidence/episode_000';paths=[Path(a['terminal']['path']),ed/'in-worker-audit-receipt.json',ed/'decision-evidence-audit.json',ep/'events.jsonl'];bs=[p.read_bytes() for p in paths]
 check(sha(bs[0])==a['terminal']['sha256'],'terminal hash')
 terminal,receipt,audit=[json.loads(b) for b in bs[:3]];index=[json.loads(s) for s in bs[3].decode().splitlines()]
 check(terminal['attempt_id']==receipt['attempt_id']==a['attempt_id'] and terminal['event']=='valid' and terminal['outcome_valid'] is True,'completed valid attempt')
 check(receipt['accepted'] is True and receipt['source']['commit']==m['source_commit'] and audit['accepted'] is True and audit['evidence_complete'] is True,'accepted native source')
 check(receipt['audit_report']==file_ref(paths[2],bs[2]),'metered audit')
 metered={str(x['path']):x['sha256'] for x in receipt['evidence']['files']}
 check(metered[str(paths[3].relative_to(out))]==sha(bs[3]),'metered index')
 all_events=[e for b in index for e in b['events']];contexts=[e for e in all_events if e['event']=='decision_context'];check(len(contexts)<=90,'boundary limit')
 wanted={'decision_context','policy_action_decode','decision_committed','final_selection'}
 selected=[b for b in index if any(e['event'] in wanted for e in b['events'])]
 bundles=[]
 for b in selected:
  p=ep/b['bundle'];check(metered[str(p.relative_to(out))]==b['sha256'],'metered selected bundle')
  bundles.append({'path':str(p.resolve()),'sha256':b['sha256'],'events':b['events']})
 by=collections.defaultdict(list)
 for e in all_events:by[e['decision_id']].append(e)
 metadata=[]
 for ctx in contexts:
  es=by[ctx['decision_id']];counts=dict(collections.Counter(e['event'] for e in es));dispatch=[e for e in es if e['event']=='action_dispatch']
  metadata.append({'decision_id':ctx['decision_id'],'global_step':ctx['global_step'],'reset_sequence':ctx['reset_sequence'],'context_sequence':ctx['sequence'],'event_counts':counts,
    'dispatch_steps':[e['global_step'] for e in dispatch],'dispatch_reset_sequences':[e['reset_sequence'] for e in dispatch],
    'selected_event_sequences':{kind:[e['sequence'] for e in es if e['event']==kind] for kind in wanted}})
 items.append({'task':a['task'],'attempt_id':a['attempt_id'],'metadata_refs':[file_ref(p,b) for p,b in zip(paths,bs)],'bundle_refs':bundles,
   'boundaries':metadata,'native_audit_guided_decisions':audit.get('n5_grasp_timing_audit',{}).get('decisions',[]),
   'native_audit_observed_counts':audit['observed_counts'],'terminal_identity':{k:terminal.get(k) for k in ['attempt_id','event','outcome_valid','compute_outcome','source_commit','actions','guided_chunks','unguided_chunks']}})
result={'schema':'n23-planned-gripper-continuity-frozen-read-scope-v1','frozen_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':file_ref(scope,sb),'attempt_manifest':file_ref(manifest,mb),'source_commit':m['source_commit'],'source_files':refs,'attempts':items,'limits':{'attempts':4,'boundaries_per_attempt':90,'boundaries_total':360,'cpu_threads':2},'blocked_reads':blocked,'reading_rule':'Only selected/context/decode/commit/final events are analyzed from listed hash-linked bundles; no canonical-history scan. Terminal population availability only if already in selected bundle.'}
f=HERE/'read-scope-v1.json';check(not f.exists(),'immutable manifest');f.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'manifest':file_ref(f),'counts':[{'task':x['task'],'boundaries':len(x['boundaries']),'selected_bundles':len(x['bundle_refs'])} for x in items],'blocked_reads':blocked},indent=2))
