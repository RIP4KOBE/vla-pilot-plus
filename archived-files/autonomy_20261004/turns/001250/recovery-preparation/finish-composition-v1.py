"""Bounded preparation only; immutable outputs and read-only owner accounting."""
import os, sys, json, hashlib, subprocess, datetime as dt, time, resource, copy, traceback
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=Path.cwd().resolve()
OWNER=Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree')
OLD=OUT.parents[1]/'001229/runtime-rebind'
STOPS=[OWNER.parent/'autonomy_20261004/STOP',ROOT.parents[2]/'autonomy_20261004/STOP']
START=time.monotonic()
resource.setrlimit(resource.RLIMIT_CPU,(600,600))
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
def forbidden(path):
    return any(x in str(path).lower() for x in ('poe','superpowers','2026-08-10-eds-qd-stage-guidance-transition-design','/.git-credentials','/.codex/auth.json','/credentials.json','/credentials/'))
def audit(event,args):
    if event=='open' and isinstance(args[0],(str,bytes)) and forbidden(args[0]):
        raise PermissionError('prohibited path access blocked: '+str(args[0]))
sys.addaudithook(audit)
def guard():
    assert not any(os.path.lexists(p) for p in STOPS), 'STOP present'
    assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
    assert time.monotonic()-START<900 and os.environ['CUDA_VISIBLE_DEVICES']==''
def sha(path):
    assert not forbidden(path)
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def ref(path):
    path=Path(path).resolve();return {'path':str(path),'sha256':sha(path)}
def read(r):
    assert sha(r['path'])==r['sha256'];return json.loads(Path(r['path']).read_text())
def write(name,value):
    guard();p=OUT/name;assert p.is_relative_to(OUT);p.parent.mkdir(parents=True,exist_ok=True)
    content=json.dumps(value,indent=2,allow_nan=False)+'\n'
    if p.exists():
        assert p.read_text()==content, 'immutable existing artifact differs: '+name
    else:p.write_text(content)
    return ref(p)
def git(root,*args):
    return subprocess.check_output(['git','--no-optional-locks','--no-replace-objects','-C',str(root),*args],env={**os.environ,'GIT_NO_LAZY_FETCH':'1'}).decode().strip()
CHECKS={}
def check(name,fn):
    guard();start=time.monotonic()
    try:
        value=fn();CHECKS[name]={'status':'PASS','wall_seconds':time.monotonic()-start};print(name,'PASS',flush=True);return value
    except Exception as e:
        CHECKS[name]={'status':'FAIL','wall_seconds':time.monotonic()-start,'error':repr(e)};raise

def main():
    sys.path.insert(0,str(ROOT))
    from scripts import qd_ed_n36_contract as c, qd_ed_n36_bridge as b, qd_ed_n36r2_draft as r2
    prior=read(ref(OLD/'composition-result-v1.json'));oldplan=read(prior['plan']);runtime=read(prior['runtime'])
    before=read(ref(OUT/'preservation-before-v1.json'))
    sr=ref(OUT/'source.permitted-only-v1.json');source=read(sr)
    cr=ref(OUT/'runtime-closure.n36r2.draft-v1.json')
    pr=ref(OUT/'protocol.n36r2.draft-v1.json');acc=ref(OUT/'accounting.n36r2.draft-v1.json');alloc=ref(OUT/'allocation.n36r2.draft-v1.json')
    rows=c.expected_rows(ROOT,cohort=c.DRAFT_RECOVERY_COHORT)
    CHECKS.update(read(ref(OUT/'preparation-failure-v2.json'))['checks'])
    plan=copy.deepcopy(oldplan)
    plan.update(cohort=c.DRAFT_RECOVERY_COHORT,worktree=str(ROOT),source=source,scientific_source=source,
          episodes=rows,artifact_root=str(OUT/'draft/prospective-artifacts'),protocol=pr,accounting=acc,
          runtime_closure=cr,expected_manifests={},stop_path=c.stop_path(ROOT),runtime_ready=False,
          readiness_scope='INCOMPLETE CPU draft only: excluded source, unrebound owner runtime, canonical STOP mismatch',
          source_coverage_complete=False,release_enabled=False,frozen=False,gpu_dispatch_authorized=False)
    check('draft_protocol_accounting_structure',lambda:r2.validate_protocol(plan))
    compositions=[]
    for row,oldrow in zip(rows,oldplan['episodes']):
        guard();m=b.manifest(plan,runtime,row)
        assert not Path(m['output_dir']).exists() and row['episode_key'] in m['output_dir']
        old=read(oldplan['expected_manifests'][oldrow['episode_key']])
        def normalized(config):
            config=json.loads(json.dumps(config))
            for key in ('n34_runtime_binding','n36_runtime_binding'):
                if config.get(key):
                    config[key]['source_commit']='<prospective-source>'
                    config[key]['run_id']='<prospective-episode>'
            if config.get('mechanism_pretest'):
                config['mechanism_pretest']['run_id']='<prospective-episode>'
                config['mechanism_pretest']['output_dir']='<fresh-output>/mechanism'
            return config
        assert normalized(m['resolved_config'])==normalized(old['resolved_config'])
        assert {k:v for k,v in row.items() if k not in ('iteration','episode_key')}=={k:v for k,v in oldrow.items() if k not in ('iteration','episode_key')}
        mr=write('draft/expected/'+row['episode_key']+'.json',m)
        plan['expected_manifests'][row['episode_key']]=mr
        compositions.append({'episode_key':row['episode_key'],'manifest':mr,'output_dir':m['output_dir'],
              'scientific_config_unchanged_except_identity_and_source_binding':True})
    check('disabled_draft_structure',lambda:c.validate_draft(plan))
    planref=write('draft/plan.partial.draft-v1.json',plan)
    write('all40-partial-composition-v1.json',{'rows':compositions,'count':len(compositions),'complete_production_composition':False,
          'source_gate':'BLOCKED','canonical_stop_gate':'BLOCKED','payload_rebind':'BLOCKED','scientific_config_comparison':'PASS'})
    write('stop-binding-blocker-v1.json',{'production_stop':c.stop_path(ROOT),'canonical_owner_stop':str(STOPS[0]),
          'checked_both_absent':True,'mismatch':c.stop_path(ROOT)!=str(STOPS[0]),'guards_modified':False,'release_enabled':False})
    context=write('cpu-context-v1.json',{'schema':'n36r2-cpu-probe-context-v1','worktree':str(ROOT),'source':sr,
          'runtime_closure':cr,'runtime':prior['runtime'],'native_build':prior['native_build'],'deadline':c.DEADLINE,
          'stop_paths':[str(p) for p in STOPS],'output':str(OUT/'cpu-receipt-v1.json'),'release_enabled':False,
          'source_coverage_complete':False,'full_after_coverage':False})
    for r in before['ledgers'].values():assert sha(r['path'])==r['sha256']
    assert ref(OWNER/'research-state.yaml')==before['state'] and git(OWNER,'rev-parse','HEAD')==before['owner_head']
    write('preparation-result-v1.json',{'status':'PARTIAL_DISABLED_DRAFT_FOR_REVIEW','source':sr,'plan':planref,
          'runtime_closure':cr,'native_build':prior['native_build'],'accounting':acc,'protocol':pr,'allocation':alloc,
          'context':context,'checks':CHECKS,'elapsed_seconds':time.monotonic()-START,
          'cpu_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime,
          'release_enabled':False,'gpu_authorized':False})

if __name__=='__main__':
    try:main()
    except Exception as e:
        write('composition-failure-v3.json',{'error':repr(e),'traceback':traceback.format_exc(),'checks':CHECKS})
        raise
