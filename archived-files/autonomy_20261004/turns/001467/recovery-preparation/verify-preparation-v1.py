"""Read-only focused artifact checks. No imports of production/model modules."""
import os,sys,json,hashlib,datetime as dt,subprocess,resource,signal
from pathlib import Path
OUT=Path(__file__).absolute().parent
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_CPU,(60,60));signal.alarm(60)
os.environ.update(CUDA_VISIBLE_DEVICES='',GIT_OPTIONAL_LOCKS='0',GIT_NO_LAZY_FETCH='1')
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bound(r):
 assert sha(r['path'])==r['sha256'],r['path']
 return load(r['path'])
p=load(OUT/'plan.draft.json');a=bound(p['accounting']);authority=load(OUT/'authority-v1.json')
for path in p['stop_authority']['paths']:
 try:os.lstat(path)
 except FileNotFoundError:pass
 else:raise AssertionError('STOP present: '+path)
now=dt.datetime.now(dt.timezone.utc);deadline=dt.datetime.fromisoformat(p['deadline'].replace('Z','+00:00'));assert now<deadline
root=p['worktree'];head=subprocess.check_output(['git','-C',root,'rev-parse','HEAD'],text=True).strip();assert head==authority['source']==p['source']['commit']
assert not subprocess.check_output(['git','-C',root,'status','--porcelain','--untracked-files=no'],text=True)
assert p['cohort']=='N36R4_NONPROGRESS_TANGENT_DEV_001467'
assert p['frozen'] is False and p['release_enabled'] is False and p['root_review'] is p['authority'] is p['execution_release'] is None
assert not any(p['phase_authorization'].values()) and p['expected_manifests']=={}
assert p['source']==p['scientific_source']
for r in p['source']['files']:assert sha(Path(root)/r['path'])==r['sha256']
for k in ('runtime','runtime_closure','native_build','controller_semantics','protocol','accounting'):bound(p[k])
runtime=bound(p['runtime']);closure=bound(p['runtime_closure']);assert closure['runtime']==p['runtime']
assert runtime['preparation']['runtime_ready'] is False and runtime['cuda_egl_probe'] is None and runtime['provider_ready'] is False and runtime['cuda_egl_verified'] is False
assert len(p['episodes'])==len(p['prospective_manifests'])==40
assert [r['task_id'] for r in p['episodes']]==[i for i in range(10) for _ in range(4)]
assert [r['profile'] for r in p['episodes']]==['C0','Q0','N34','N36']*10
assert len({r['episode_key'] for r in p['episodes']})==40
old=bound(bound(p['protocol'])['previous_plan'])
for r,prior in zip(p['episodes'],old['episodes']):
 assert {k:v for k,v in r.items() if k not in ('iteration','episode_key')}=={k:v for k,v in prior.items() if k not in ('iteration','episode_key')}
 m=bound(p['prospective_manifests'][r['episode_key']]);assert m['row']==r and m['cohort']==p['cohort'] and m['release_enabled'] is False
 assert r['episode_key'].endswith('_001467') and r['iteration']==p['cohort']
 for k in ('source','scientific_source','runtime','runtime_closure','native_build','controller_semantics','protocol','accounting','resource_routing'):assert m[k]==p[k]
 assert Path(m['output_dir']).is_relative_to(OUT) and m['production_manifest_validation']=='BLOCKED_UNSUPPORTED_COHORT'
 for arg in m['argv']:
  if arg.startswith(('hydra.run.dir=','main.eds_eval.output_dir=','main.eds_eval.report_dir=','main.eds_mechanism_pretest.output_dir=')):assert Path(arg.split('=',1)[1]).is_relative_to(OUT)
health=load(OUT/'health-policy.disabled-v1.json');assert health['preparation_id']=='n36_healthcheck_n36r4_preparation_001467' and health['readiness'] is None
assert health['episode_health_ids']==['n36_healthcheck_'+r['episode_key'] for r in p['episodes']]
assert a['retained_attempts']==506 and a['prospective_attempts']==546 and a['hours']['retained']=='75.60616276674473'
assert a['protected_remaining_attempts']=={'validation':120,'formal':40}
for r in a['retained_ledger_prefixes'].values():assert Path(r['path']).stat().st_size==r['bytes'] and sha(r['path'])==r['sha256']
if (OUT/'report-v1.json').exists():
 report=load(OUT/'report-v1.json')
 for r in report['artifacts'].values():assert sha(r['path'])==r['sha256']
 assert report['score'] is None and report['goal_complete'] is False and report['release_enabled'] is False
print(json.dumps({'status':'PASS_FOCUSED_DISABLED_ARTIFACT_CONSISTENCY','source':head,'prospective_manifests':40,'production_manifests':0,'production_release_blocked':True,'checked_at':now.isoformat(),'remaining_wall_seconds':(deadline-now).total_seconds(),'full_21h_window_currently_fits':(deadline-now).total_seconds()>=75600,'model_construction_coverage':False}))
