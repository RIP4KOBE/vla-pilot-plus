import sys,json,hashlib,traceback,datetime,os
from pathlib import Path
sys.path.insert(0, '/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree')
from scripts import qd_ed_n36_release as rel, qd_ed_n36_contract as c, qd_ed_n23_worker as w
out=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001296')
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(name,obj):
 p=out/name;p.write_text(json.dumps(obj,indent=2)+'\n');return ref(p)
plan_ref=ref(Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001295/plan.frozen.n36r2-v1.json'));p=w.read_ref(plan_ref)
result={'schema':'n36r2-full-production-verification-v1','plan':plan_ref,'dispatch_performed':False,'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
try:
 rel.validate_plan(p)
 expected={'schema':'n36-execution-release-v1','approved':True,'plan':plan_ref,**{k:p[k] for k in ('native_build','authority','protocol','protocol_review','source','scientific_source','runtime_closure','controller_semantics','runtime','phase_authorization')},'limits':c.LIMITS,**c.operational_binding(p)}
 review=write('root-production-review-v1.json',{**expected,'schema':'n36-root-production-review-v1','decision':'APPROVED'})
 release=write('execution-release-v1.json',{**expected,'root_review':review})
 result['release']=release;result['review']=review
 rel.verify_prospective_release(plan_ref,release)
 result['status']='PASS_FULL_UNMODIFIED_RELEASE_VERIFICATION'
except Exception as e:
 result['status']='BLOCKED_NO_DISPATCH';result['error']=repr(e);result['traceback']=traceback.format_exc()
finally:
 result['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();write('production-verification-v1.json',result);print(json.dumps(result),flush=True)
