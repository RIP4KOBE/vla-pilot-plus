import json,pathlib,hashlib,datetime,sys,os,subprocess,yaml
root=pathlib.Path.cwd(); turns=(root.parent/'autonomy_20261004/turns').resolve(); out=turns/'000917'
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def read(r):
 assert ref(r['path'])==r,r;return json.load(open(r['path']))
def write(name,d):
 p=out/name;assert not p.exists();p.write_text(json.dumps(d,indent=2)+'\n');return ref(p)
s=yaml.safe_load((root/'research-state.yaml').read_text());now=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert not (root.parent/'autonomy_20261004/STOP').exists()
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()=='52a87af0bf11f95b21ce17aba456dc98944d9774'
review=read(s['n35_runtime_rebinding']); supplement=read(s['n35_pre_release_accounting']); plan=read(review['disabled_draft']); runtime=read(plan['runtime'])
for v in supplement['ledger_prefixes'].values():assert ref(v['path'])['sha256']==v['sha256']
for k in ['n35_protocol_root_acceptance','n35_audit_repair_root_acceptance','n35_source_adoption']:read(s[k])
protocol=read(s['n35_prospective_protocol']);read(protocol['accounting'])
os.environ.update(runtime['environment']);os.environ['CUDA_VISIBLE_DEVICES']='';sys.path[:0]=[str(root)]+runtime['environment']['PYTHONPATH'].split(':')
from scripts import qd_ed_n35_contract as c,qd_ed_n35_release as release
c.validate_draft(plan)
a={'schema':'n35-budget-authority-v1','approved':True,'cohort':c.COHORT,'limits':c.LIMITS,'caps':c.CAPS,'validation_authorized':False,'formal_authorized':False,'coordinator_ends_at':c.DEADLINE,'automatic_recoveries':0,'protocol':s['n35_prospective_protocol'],'accounting':protocol['accounting'],'starts_at':now,'weekly_window':{'ends_at':c.DEADLINE,'origin_gpu_hours':53.08404692669838,'increment_gpu_hours':168.0},'approval_basis':protocol['authority'],'ledger_prefixes':supplement['ledger_prefixes'],'supplemental_accounting':s['n35_pre_release_accounting'],'previous_amendment':s['budget']['amendment'],'amendment':{'approval':protocol['authority'],'prospective_accounting':protocol['accounting'],'pre_release_accounting':s['n35_pre_release_accounting'],'history_boundary':{'dispatched':474,'conservative_gpu_hours':supplement['current_conservative_charge']},'scope':'N35 fresh all40 Dev only; 21 GPU hours inclusive of preparation, zero automatic recovery; unchanged cumulative caps and protected reserves.'}}
ar=write('budget-authority-v1.json',a)
plan.update(schema='n35-released-plan-v1',frozen=True,release_enabled=True,authority=ar,protocol=s['n35_prospective_protocol'],attempt_identity='episode_key',run_name=s['run_name'],phase_authorization={'dev':True,'validation':False,'formal':False})
for k in ['root_review','execution_release']:del plan[k]
pr=write('plan.frozen-v1.json',plan)
expected={'schema':'n35-execution-release-v1','approved':True,'plan':pr,**{k:plan[k] for k in ['authority','protocol','source','scientific_source','runtime_closure','controller_semantics','runtime','limits','phase_authorization']}}
rr=write('root-production-review-v1.json',{**expected,'schema':'n35-root-production-review-v1','decision':'APPROVED'})
er=write('execution-release-v1.json',{**expected,'root_review':rr})
try:
 release.validate_release(pr,er)
 write('public-release-validation-v1.json',{'status':'PASS','plan':pr,'release':er,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'gpu_dispatched':False,'state_adopted':False})
 print('PASS',pr,er)
except Exception as e:
 write('public-release-validation-v1.json',{'status':'FAIL','plan':pr,'release':er,'error':repr(e),'gpu_dispatched':False,'state_adopted':False});raise
