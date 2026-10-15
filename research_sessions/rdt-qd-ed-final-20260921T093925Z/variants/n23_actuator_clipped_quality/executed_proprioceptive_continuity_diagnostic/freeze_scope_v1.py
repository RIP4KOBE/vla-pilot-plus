from pathlib import Path
import hashlib,json,datetime,sys,os
H=Path(__file__).resolve().parent;V=H.parent;R=V.parents[1]
def digest(b):return hashlib.sha256(b).hexdigest()
def ref(p,b=None):return {'path':str(p.resolve()),'sha256':digest(p.read_bytes() if b is None else b)}
def check(x,m):
 if not x:raise ValueError(m)
s=V/'executed-proprioceptive-continuity-scope-v1.md';m=V/'planned-gripper-continuity-attempts-v1.json';prior=V/'planned_gripper_continuity_diagnostic';rs=prior/'read-scope-v1.json';dr=prior/'result-v1.json'
sb=s.read_bytes();mb=m.read_bytes();rb=rs.read_bytes();db=dr.read_bytes()
check(digest(sb)=='6079124108909718e89d0158bb7a4c13bf03e3f23cffdc0981162fd34740943d','scope')
check(digest(mb)=='cca36ad827d720aa7973e808d86db7fb00da961f44ba4203f57123626adc39f4','attempt manifest')
check(digest(rb)=='65e0381d8ad3e1e9321be09b63e5cbf5a11ece46f1950adf76a2aceed640d452','prior readscope')
check(digest(db)=='2e12365b15cff7e656a4468a4ad22cb238e34d0c5155ad13c332cacd' if False else digest(db)=='2e12365b15cff7e656a4468a4ad22cb238e34d0c5155ad0294a5fd13c332cacd','prior derived')
old=json.loads(rb);derived=json.loads(db);attempts=json.loads(mb)
allowed={str(Path(a['metadata_refs'][3]['path']).resolve()) for a in old['attempts']};blocked=[]
def guard(e,args):
 if e!='open':return
 p,mode,flags=args
 if isinstance(p,int):return
 p=str(Path(os.fsdecode(p)).resolve());write=bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
 if p.startswith(str(R.resolve())+'/') or p.startswith('/mnt/data/shared2/hynx/VLA-Pilot++/'):
  if write and not p.startswith(str(H)+'/'):raise RuntimeError('write scope')
  if not write and p not in allowed and not p.startswith(str(H)+'/'):blocked.append(p);raise RuntimeError('read scope')
sys.addaudithook(guard)
wanted={'action_dispatch','executed_action','pre_reset_outcome','step_returned','policy_action_decode','decision_committed'};items=[]
for a in old['attempts']:
 ri=a['metadata_refs'][3];p=Path(ri['path']);b=p.read_bytes();check(digest(b)==ri['sha256'],'index changed')
 idx=[json.loads(line) for line in b.decode().splitlines()];bundles=[]
 for item in idx:
  if any(e['event'] in wanted for e in item['events']):bundles.append({'path':str((p.parent/item['bundle']).resolve()),'sha256':item['sha256'],'events':item['events']})
 contexts=[x for x in derived['boundaries'] if x['task']==a['task']]
 check(a['attempt_id']==attempts['attempts'][a['task']]['attempt_id'],'attempt identity')
 counts={k:sum(e['event']==k for item in idx for e in item['events']) for k in wanted}
 check(counts['pre_reset_outcome']==counts['action_dispatch']==counts['executed_action']==counts['step_returned']==720,'2880 scope')
 items.append({'task':a['task'],'attempt_id':a['attempt_id'],'prior_metadata_refs':a['metadata_refs'],'index':ri,'bundles':bundles,'event_counts':counts,'boundaries_from_prior_derived':contexts})
out={'schema':'n23-executed-proprioception-frozen-read-scope-v1','created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':ref(s,sb),'attempt_manifest':ref(m,mb),'prior_read_scope':ref(rs,rb),'prior_derived_result':ref(dr,db),'source_commit':old['source_commit'],'source_files':old['source_files'],'attempts':items,
 'strict_full_positive_pairs':[p for p in derived['pairs'] if p.get('category')=='strict_same_guided_stage_reset_target' and p['predicted_positive_count']==8],
 'limits':{'native_screen_wall_seconds':180,'engineering_reruns':2,'actual_transitions':2880,'cpu_threads':2,'cuda_visible_devices':''},
 'allowed_observation_fields':['robot0_eef_pos','robot0_eef_quat','robot0_gripper_qpos','robot0_gripper_qvel'],'excluded_fields':['reward','success','terminated','truncated','contact','object_pose','images'],'blocked_reads':blocked}
f=H/'read-scope-v1.json';check(not f.exists(),'no overwrite');f.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'manifest':ref(f),'attempts':[{'task':a['task'],'bundles':len(a['bundles']),'transitions':a['event_counts']['pre_reset_outcome']} for a in items],'strict_pairs':len(out['strict_full_positive_pairs']),'blocked_reads':blocked},indent=2))
