import sys,json,pathlib,hashlib,datetime,os,yaml
root=pathlib.Path.cwd();sys.path.insert(0,str(root))
from scripts import qd_ed_final_runner as r
out=root.parent/'autonomy_20261004/turns/000462';now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def ref(p):
 p=pathlib.Path(p); b=p.read_bytes();return {'path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
def write(p,obj):
 assert not p.exists();p.write_text(json.dumps(obj,indent=2)+'\n')
rv=json.loads((out/'runtime-candidate-verification.json').read_text());probe=json.loads((out/'image-transport-probe-sanitized/result.json').read_text());assert rv['status']=='PASS' and probe['exit']==0 and probe['completed_turns']==1 and not probe['errors']
review={'schema':'n32r3-runtime-transport-readiness-v1','at':now,'source':rv['source'],'runtime_verification':ref(out/'runtime-candidate-verification.json'),'initial_disabled_schema_check':ref(out/'runtime-verification.json'),'image_transport':ref(out/'image-transport-probe-sanitized/result.json'),'environment_policy':ref(out/'image-transport-probe-sanitized/environment-policy.json'),'retained_initial_probe_failure':ref(out/'image-transport-probe/result.json'),'diagnosis':'Initial diagnostic launcher incompletely sanitized inherited environment (CODEX_API_KEY remained); failed authentication. Corrected diagnostic uses existing production codex_removed_environment filter. No credential files opened/modified; no provider/account fallback. Production code unchanged.','status':'PASS_RUNTIME_AND_IMAGE_TRANSPORT_ONLY','scientific_evidence':False,'release_approved':False,'gpu_dispatched':False}
write(out/'readiness-review.json',review)
next_action='N32R3 runtime and fresh official Stage image transport passed in turn462. Obtain independent detached production review of accounted-composition-input-v1.json, freeze/validate external release, then fresh GPU7 admission before dispatch. Use production child_environment/codex_removed_environment for every CLI child; never inherit alternate key overrides. Preserve 14 valid cells and invalid task4 charge.'
with r.locked(root/'data/qd-ed-state.lock'):
 sp=root/'research-state.yaml'; cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'; tp=cp.parent/'idea_tree.json'
 s=yaml.safe_load(sp.read_text());c=json.loads(cp.read_text());t=json.loads(tp.read_text());assert s['active_controller'] is None and not s['current_owned_workers']
 entry=json.loads((out/'entry-reconciliation.json').read_text());assert all(ref(x['path'])==x for x in entry['ledger_prefixes'])
 for p in [sp,cp,tp]: (out/('pre-readiness-'+p.name)).write_bytes(p.read_bytes())
 rr=ref(out/'readiness-review.json')
 for obj in [s,c]:obj['n32r3_runtime_transport_readiness']=rr;obj['next_action']=next_action;obj['updated_at']=now
 node=t['nodes']['15.2'];node['n32r3_runtime_transport_readiness']=rr;node['result']='N32R3 operational source and accounting adopted; frozen runtime and fresh official image transport passed. Detached production release review pending; no GPU dispatch or promotion. Prior 14 valid cells and invalid charge preserved.'
 for p,obj,is_yaml in [(sp,s,True),(cp,c,False),(tp,t,False)]:
  temp=p.with_name(p.name+'.turn462.tmp');temp.write_text(yaml.safe_dump(obj,sort_keys=False) if is_yaml else json.dumps(obj,indent=2)+'\n');os.replace(temp,p)
 write(out/'state-reconciliation.json',{'at':now,'state':ref(sp),'checkpoint':ref(cp),'tree':ref(tp),'ledger_unchanged':True,'gpu_dispatched':False})
summary=f'''Current source: {rv['source']}; scientific source unchanged.
Live handles: driver268073/start97715947; coordinator965121/start132139844; boot2a1fa95f-ab0d-488c-a298-fc488ddd2af7. No GPU cohort/executor running; prior controller1818171 absent. GPU7 observed idle. STOP absent; cohort deadline2026-10-10T17:42:00Z; authorization ends2026-10-11T11:13:13Z.
Completed: hash-bound entry and prior normal turn reconciled. Verified562 source files and3291 runtime entries plus full frozen model/task/seed inputs. Initial disabled-schema runtime check rejected recovery routing; pure in-memory candidate-schema check passed without release authority. First diagnostic launcher incompletely filtered inherited credential overrides and failed; retained result. Corrected diagnostic uses production filter, passed one official gpt-6-astra image turn (9256 input/31 output tokens). No credential files opened/modified. No source changes, GPU dispatch, ledger changes, or scientific claims. Owning state/checkpoint/node15.2 linked to readiness-review.json.
Next bounded step: {next_action}
Unresolved: detached production review/release validation and fresh GPU admission. Existing438 attempts/61.35722319715016GPUh retained; reserved validation/formal intact. Validation/formal/required ablation and completion record remain absent; original goal unmet. Driver retains its own locks and continues.
'''
(out/'operational-summary.md').write_text(summary);print(json.dumps({'review':rr,'summary':ref(out/'operational-summary.md')}))
