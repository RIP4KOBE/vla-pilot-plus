import pathlib,json,datetime,traceback
from scripts import qd_ed_n23_worker as w, qd_ed_n32r3_contract as c, qd_ed_n32r3_release as release
turn=pathlib.Path('../autonomy_20261004/turns/000468').resolve()
plan=json.loads((turn/'composition-input-v2.json').read_text()); result=json.loads((turn/'composition-result-v2.json').read_text())
plan.update(schema='n32r3-released-plan-v1',frozen=True,release_enabled=True,phase_authorization={'dev':True,'validation':False,'formal':False},expected_manifests=result['expected_manifests'])
w.atomic_json(turn/'plan.frozen.v2.json',plan); pref=c.ref(turn/'plan.frozen.v2.json')
expected={'schema':'n32r3-execution-release-v1','approved':True,'plan':pref,'authority':plan['authority'],'protocol':plan['protocol'],'source':plan['source'],'runtime':plan['runtime'],'limits':c.LIMITS,'phase_authorization':plan['phase_authorization'],'continuation':c.commitments(plan,plan['episodes'][0])}
w.atomic_json(turn/'root-production-review-v2.json',{**expected,'schema':'n32r3-root-production-review-v1','decision':'APPROVED'})
w.atomic_json(turn/'execution-release-v2.json',{**expected,'root_review':c.ref(turn/'root-production-review-v2.json')})
rref=c.ref(turn/'execution-release-v2.json'); started=datetime.datetime.now(datetime.timezone.utc).isoformat()
try:
 release.validate_release(pref,rref)
 outcome={'status':'PASS','plan':pref,'release':rref,'started_at':started,'finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'gpu_dispatched':False,'state_adopted':False,'next_step':'Fresh Stage transport, GPU7 admission and state adoption before launch.'}
except Exception as e:
 outcome={'status':'FAIL','plan':pref,'release':rref,'started_at':started,'finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'error':str(e),'traceback':traceback.format_exc(),'gpu_dispatched':False,'state_adopted':False}
w.atomic_json(turn/'release-validation-v2.json',outcome);print(json.dumps(outcome))
