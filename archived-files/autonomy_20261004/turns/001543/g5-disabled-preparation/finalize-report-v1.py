"""Bounded independent artifact cross-check. No source/provenance rebuild."""
import datetime as dt
import hashlib
import json
import os
import subprocess
from pathlib import Path

B=Path(__file__).resolve().parent
ROOT=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
os.environ.update(GIT_OPTIONAL_LOCKS='0',GIT_NO_LAZY_FETCH='1')
DEADLINE=dt.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
for p in (B.parents[2]/'STOP',ROOT.parents[2]/'autonomy_20261004/STOP'):
    try:p.lstat()
    except FileNotFoundError:pass
    else:raise ValueError('STOP present')
assert dt.datetime.now(dt.timezone.utc)<DEADLINE

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(p),'bytes':Path(p).stat().st_size,'sha256':sha(p)}
def read(p):return json.loads(Path(p).read_text())
def verify(r):
    assert sha(r['path'])==r['sha256'],r['path']
    if 'bytes' in r:assert Path(r['path']).stat().st_size==r['bytes'],r['path']

attempt=B/'attempt-2/report-v1.json';report=read(attempt)
assert report['status']=='PASS' and report['counts']=={'original_rows':40,'audit_manifests':40,'diagnostic_manifests':1}
for r in report['outputs'].values():verify(r)
authority=read(B/'authority-v1.json');source=read(authority['accepted_g2_source']['path'])
index={row['path']:row['sha256'] for row in source['files']}
checked=0
for r in report['inputs']:
    p=Path(r['path'])
    if p.is_relative_to(ROOT) and str(p.relative_to(ROOT)) in index:
        assert r['sha256']==index[str(p.relative_to(ROOT))]
        assert sha(p)==r['sha256']
        checked+=1
audit=read(report['outputs']['audit-view.disabled-v1.json']['path'])
plan=read(report['outputs']['engineering-plan.disabled-v1.json']['path'])
original=read(audit['original_plan']['path']);verify(audit['original_plan'])
for k in ('cohort','episodes','limits','worker_contract','deadline','protocol','protocol_review','accounting'):
    assert audit[k]==original[k],k
assert len(audit['episodes'])==40
assert [r['task_id'] for r in audit['episodes']]==[i for i in range(10) for _ in range(4)]
assert [r['profile'] for r in audit['episodes']]==['C0','Q0','N34','N36']*10
assert set(audit['expected_manifests'])=={r['episode_key'] for r in audit['episodes']}
paths=set()
for row in audit['episodes']:
    mr=audit['expected_manifests'][row['episode_key']];verify(mr);m=read(mr['path'])
    assert m['row']==row and m['dispatch_authority'] is False
    for k in ('source','scientific_source','native_build','runtime','runtime_closure','controller_semantics','scope','deployment'):
        assert m[k]==audit[k],k
    assert Path(m['output_dir']).is_relative_to(Path(audit['artifact_root']))
    paths.add(m['output_dir'])
assert len(paths)==40
assert plan['release_enabled'] is False and plan['frozen'] is False
assert plan['authority'] is None and plan['b5_review'] is None
assert all(v is False for v in plan['phase_authorization'].values())
verify(plan['engineering_manifest']);m=read(plan['engineering_manifest']['path'])
assert m['audit_row']==audit['episodes'][0]
assert m['row']=={**audit['episodes'][0],'iteration':plan['cohort'],'episode_key':plan['episodes'][0]['episode_key']}
assert all(m[k] is False for k in ('scientific_eligible','matched_improvement_eligible','promotion_eligible'))
assert m['output_dir'] not in paths
assert read(plan['accounting']['path'])['root_adopted'] is False
assert read(plan['controller_semantics']['path'])['status']=='DISABLED_PENDING_ROOT_REVIEW'
assert not Path(plan['artifact_root']).exists()
prefixes={}
for name,r in authority['ledger_prefixes'].items():
    with Path(r['path']).open('rb') as f:digest=hashlib.sha256(f.read(r['bytes'])).hexdigest()
    assert digest==r['sha256']
    prefixes[name]={**r,'prefix_agrees':True,'current_bytes':Path(r['path']).stat().st_size,'suffix_bytes':Path(r['path']).stat().st_size-r['bytes']}
assert subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()==authority['source']
assert not subprocess.check_output(['git','-C',str(ROOT),'diff','--name-only',authority['source'],'--'],text=True).strip()
failed=ref(B/'report-attempt-1-v1.json');verify(failed)
report['artifact_generation_report']=ref(attempt)
report['retained_failed_attempts']=[{'report':failed,'reason':'Passive helper namespace omitted SEPARATE_HEALTH_COHORTS; corrected only artifact helper in attempt-2. Candidate unchanged.'}]
report['inputs'].extend([ref(B/'finalize-report-v1.py'),ref(attempt),failed])
report['checks']['independent_final_artifact_crosscheck']={'status':'PASS','output_hashes_checked':len(report['outputs']),'candidate_accessed_files_match_accepted_G2':checked,'original_rows_and_gates_equal':True,'task_major_arm_order':True,'unique_audit_outputs':40,'fresh_diagnostic_output_identity':True,'disabled_accounting_and_controller_review':True,'dedicated_execution_output_absent':True,'tracked_candidate_unchanged':True,'no_broad_tests':True}
report['retained_ledger_prefixes']=prefixes
report['retained_accounting']={'attempts':506,'gpu_hours':'75.60616276674473','new_attempts':0,'new_gpu_charge':0,'source':'accepted G5 authority/specification and G3/G4 root review; all three ledger prefixes unchanged','prospective_reservation_seconds':1900,'prospective_wall_seconds':2100,'adopted':False}
report['configuration_composition']={'method':'Exact candidate compose_launch with installed Hydra/OmegaConf pure-Python composition; optional yaml._yaml native accelerator import denied before load and PyYAML used its standard pure-Python fallback. No helper or verification semantics rewritten.','model_native_simulator_provider_imports':False,'provider_invocation':False,'public_provider_configuration_only':True}
report['finalized_at']=dt.datetime.now(dt.timezone.utc).isoformat()
with (B/'report-v1.json').open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
print(json.dumps({'status':report['status'],'counts':report['counts'],'outputs_verified':len(report['outputs']),'report':ref(B/'report-v1.json'),'retained_failed_attempts':1}))
