import json,datetime,pathlib,traceback
from scripts import qd_ed_n32r3_contract as c, qd_ed_n32r3_release as release, qd_ed_n23_worker as w
root=pathlib.Path.cwd(); out=root.parent/'autonomy_20261004/turns/000463'; dest=root.parent/'variants/n32_archive_eligible_capture/root-continuation-release-v3'
p=json.loads((dest/'accounted-composition-input-v1.json').read_text())
assert not pathlib.Path(p['stop_path']).exists()
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(p['deadline'].replace('Z','+00:00'))
p.update(schema='n32r3-released-plan-v1',frozen=True,release_enabled=True,phase_authorization={'dev':True,'validation':False,'formal':False})
release.validate_plan(p)
release.verify_continuity(p)
from scripts.qd_ed_n32r3_history import validate_mapping
validate_mapping(p)
review={'schema':'n32r3-root-production-rationale-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reviewer':'root coordinator independent of implementation executor','source':p['source']['commit'],'basis':[c.ref(root.parent/f'autonomy_20261004/turns/{n}/{f}') for n,f in [('000458','implementation-root-review.json'),('000460','composition-review.json'),('000461','accounting-adoption.json'),('000462','readiness-review.json')]],'findings':['14 historical accepted cells remain bound to original receipt closure; invalid task4 charge retained.','Exactly16 new cells: one explicit recovery plus task5-9 matched C0/Q0/N32; no automatic retries.','Scientific source and audits unchanged; reviewed operational recovery routing only.','Accounting retains438 attempts and61.35722319715016GPUh; continuation16 attempts/8.5GPUh; protected reserves unchanged.','Same-process native/generic audits and complete-triple futility retained; validation/formal remain unauthorized.'],'decision':'APPROVE_DETACHED_RELEASE_SUBJECT_TO_FULL_VALIDATOR_AND_LIVE_ADMISSION','delegation':'collaboration spawn failed: no thread; no child launched. Root performed review against separate executor implementation and existing independent reviews.','gpu_dispatched':False}
w.atomic_json(out/'production-review-rationale.json',review)
for file in ['plan.frozen.v1.json','root-production-review-v1.json','execution-release-v1.json']: assert not (dest/file).exists()
w.atomic_json(dest/'plan.frozen.v1.json',p); pr=c.ref(dest/'plan.frozen.v1.json')
expected={'schema':'n32r3-execution-release-v1','approved':True,'plan':pr,'authority':p['authority'],'protocol':p['protocol'],'source':p['source'],'runtime':p['runtime'],'limits':c.LIMITS,'phase_authorization':p['phase_authorization'],'continuation':c.commitments(p,p['episodes'][0])}
w.atomic_json(dest/'root-production-review-v1.json',{**expected,'schema':'n32r3-root-production-review-v1','decision':'APPROVED'})
w.atomic_json(dest/'execution-release-v1.json',{**expected,'root_review':c.ref(dest/'root-production-review-v1.json')})
rr=c.ref(dest/'execution-release-v1.json')
try:
 release.validate_release(pr,rr)
 result={'status':'PASS','plan':pr,'release':rr,'rationale':c.ref(out/'production-review-rationale.json'),'gpu_dispatched':False}
except Exception as e:
 result={'status':'FAIL','plan':pr,'release':rr,'error':str(e),'traceback':traceback.format_exc(),'gpu_dispatched':False}
w.atomic_json(out/'release-validation.json',result); print(json.dumps(result))
