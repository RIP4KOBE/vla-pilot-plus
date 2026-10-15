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
    guard();assert git(OWNER,'rev-parse','HEAD')=='ca4e6a96d049c7ebb1f302d755883388ddbfdbd8'
    acceptance=read(ref(OWNER.parent/'autonomy_20261004/turns/001249/root-source-acceptance-v1.json'))
    assert acceptance['accepted_isolated_commit']=='e95745853ec2fbb95e55915e99644a4dc0443261'
    for r in acceptance['ledger_prefixes'].values():assert sha(r['path'])==r['sha256'] and Path(r['path']).stat().st_size==r['bytes']
    before={'owner_head':git(OWNER,'rev-parse','HEAD'),'ledgers':acceptance['ledger_prefixes'],
            'state':ref(OWNER/'research-state.yaml'),'stops':{str(p):os.path.lexists(p) for p in STOPS}}
    write('preservation-before-v1.json',before)
    prior=read(ref(OLD/'composition-result-v1.json'));oldplan=read(prior['plan']);runtime=read(prior['runtime']);oldclosure=read(prior['runtime_closure'])
    sys.path.insert(0,str(ROOT))
    from scripts import qd_ed_n36_contract as c, qd_ed_n36_bridge as b, qd_ed_n34_source as s
    from scripts import qd_ed_n36r2_draft as r2, qd_ed_final_runner as runner, qd_ed_n36_build as native
    # Restore only pinned source/config blobs to this isolated checkout, no git
    # configuration, owner checkout edits, package installation or network fetch.
    materialized=[]
    for sub in s.PINNED_SUBMODULES:
        pin,db=s.submodule_pin(ROOT,sub);entries=s._source_tree(ROOT,pin,db)
        names=sorted(s.submodule_paths(ROOT,sub))
        assert not any(forbidden(n) for n in names)
        selected={n:entries[n[len(sub)+1:]][2] for n in names}
        blobs=s._source_blobs(ROOT,selected.values(),db)
        for n,blob in selected.items():
            p=ROOT/n;data=blobs[blob]
            if p.exists():assert p.read_bytes()==data
            else:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        materialized.append({'submodule':sub,'pin':pin,'read_only_database':str(db),'files':len(selected)})
    write('materialized-pinned-source-v1.json',materialized)
    paths=b.source_paths(ROOT);excluded=sorted(p for p in paths if forbidden(p));assert excluded==['scripts/qd_ed_poe_launch.py'],excluded
    source=check('permitted_git_source_record',lambda:s.source_record(ROOT,paths-set(excluded)))
    sr=write('source.permitted-only-v1.json',source)
    write('source-coverage-v1.json',{'source':sr,'complete':False,'excluded_without_opening':excluded,'source_commit':source['commit'],
          'accepted_base':acceptance['accepted_isolated_commit'],'materialized':materialized,'complete_source_gate':'BLOCKED: prohibited file is a required production inventory member'})
    # Preserve every ordinary entry. Alias rules never replace/shrink inventory.
    closure=copy.deepcopy(oldclosure)
    closure['module_aliases']=s.build_cyutility_alias_rule(closure['modules'])
    closure['required_after']=list(closure['required_after'])+['_cyutility']
    cr=write('runtime-closure.n36r2.draft-v1.json',closure)
    check('full_ordinary_runtime_closure',lambda:s.verify_runtime(closure,prior['runtime']))
    assert closure['modules']==oldclosure['modules'] and closure['generated_modules']==oldclosure['generated_modules']
    payload=check('runtime_payload_files',lambda:b.runner.verify_files(runtime['files'],allowed_roots=(str(OWNER),runtime['artifact_root'])))
    write('runtime-payload-reuse-v1.json',{'runtime':prior['runtime'],'runtime_closure':cr,'prior_closure':prior['runtime_closure'],
          'ordinary_count':len(closure['modules']),'ordinary_inventory_unchanged':True,'file_count':len(runtime['files']),
          'all_runtime_payload_files_verified':True,'relocated':False,'payload_owner_worktree':runtime['worktree'],
          'candidate_worktree':str(ROOT),'runtime_worktree_rebind_complete':False,
          'module_aliases':closure['module_aliases'],'interpreter':closure['interpreter'],
          'distribution_versions':closure['distribution_versions'],'generated_modules':closure['generated_modules'],
          'readiness':'historical references only; no device/provider evidence created','release_enabled':False})
    nb=check('native_build_static_inventory',lambda:native.manifest(prior['native_build']))
    write('native-binding-v1.json',{'native_build':prior['native_build'],'libraries':len(nb['libraries']),
           'static_hashes_verified':True,'native_gpu_evaluation':False,'same_worker_after_attestation':False})
    events=[json.loads(line) for line in (OWNER/'data/attempt-ledger.jsonl').read_text().splitlines() if line.strip()]
    resources=[json.loads(line) for line in (OWNER/'data/gpu-healthcheck-ledger.jsonl').read_text().splitlines() if line.strip()]
    snap=check('private_ledger_arithmetic',lambda:runner.budget_snapshot(events,resources))
    assert snap['dispatched']==504 and snap['gpu_hours_consumed']==75.49265038509455,snap
    preserved=[]
    for record in r2.PRESERVED:
        rows=[e for e in events if e.get('attempt_id')==record['attempt_id']]
        assert [r['event'] for r in rows]==['reserved','dispatched','aborted']
        assert rows[-1]['gpu_process_wall_seconds']==record['gpu_seconds']
        preserved.append(record)
    from decimal import Decimal,localcontext
    terminal=[e for e in events if e['event'] in ('valid','aborted')]
    health=[e for e in resources if e['event'] in ('completed','aborted')]
    with localcontext() as ctx:
        ctx.prec=60
        seconds=sum((Decimal(str(e['gpu_process_wall_seconds'])) for e in terminal+health),Decimal(0))
        exact_hours=seconds/Decimal(3600)
    snapshot=write('accounting-snapshot-v1.json',{'schema':'n36r2-read-only-ledger-snapshot-v1',**snap,
          'ledger_prefixes':before['ledgers'],'preserved_attempts':preserved,'protected_gpu_hours':c.CAPS['protected_gpu_hours'],
          'protected_attempts':{'validation':180,'formal':40},'release_enabled':False,
          'decimal_seconds_sum':str(seconds),'decimal_hours_sum':str(exact_hours),
          'float_method':'unchanged production budget_snapshot; sum episode seconds/3600 then healthcheck hours',
          'terminal_episode_count':len(terminal),'terminal_healthcheck_count':len(health),
          'dual_effective_cap_gpu_hours':min(224.,53.08404692669838+168.),
          'protected_reserve_total_gpu_hours':44.,'new_authority':False})
    rows=c.expected_rows(ROOT,cohort=c.DRAFT_RECOVERY_COHORT)
    existing={e.get('episode_key') for e in events};assert not existing & {r['episode_key'] for r in rows}
    alloc=write('allocation.n36r2.draft-v1.json',{'schema':'n36r2-allocation-draft-v1','cohort':c.DRAFT_RECOVERY_COHORT,
          'episodes':rows,'automatic_recoveries':0,'allocation_is_not_authority':True,'release_enabled':False})
    inherited=read(oldplan['protocol']);base=read(inherited['inherited_protocol'])
    acc=write('accounting.n36r2.draft-v1.json',{'schema':'n36r2-accounting-draft-v1','cohort':c.DRAFT_RECOVERY_COHORT,
          'inherited_accounting':base['accounting'],'allocation':alloc,'ledger_snapshot':snapshot,'preserved_attempts':r2.PRESERVED,
          'automatic_recoveries':0,'new_budget_authority':False,'release_enabled':False})
    pr=write('protocol.n36r2.draft-v1.json',{'schema':'n36r2-operational-protocol-draft-v1','cohort':c.DRAFT_RECOVERY_COHORT,
          'inherited_protocol':inherited['inherited_protocol'],'inherited_protocol_review':oldplan['protocol_review'],
          'accounting':acc,'allocation':alloc,'episodes':rows,'automatic_recoveries':0,'scientific_changes':False,'release_enabled':False})
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
            config=copy.deepcopy(config)
            for key in ('n34_runtime_binding','n36_runtime_binding'):
                if config.get(key):
                    config[key]['source_commit']='<prospective-source>'
                    config[key]['run_id']='<prospective-episode>'
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
        write('preparation-failure-v2.json',{'error':repr(e),'traceback':traceback.format_exc(),'checks':CHECKS})
        raise
