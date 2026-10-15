"""Bounded CPU artifact composition using unchanged production validators."""
import os, sys, json, hashlib, subprocess, datetime as dt, time, copy, traceback
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = Path.cwd().resolve()
TURNS = OUT.parent.parent
SOURCE = 'ca4e6a96d049c7ebb1f302d755883388ddbfdbd8'
STOP = ROOT.parent / 'autonomy_20261004/STOP'
START = time.monotonic()
STARTED = dt.datetime.now(dt.timezone.utc).isoformat()
CHECKS = {}
def guard():
    assert not os.path.lexists(STOP), 'STOP present'
    assert dt.datetime.now(dt.timezone.utc) < dt.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
    assert time.monotonic() - START < 1500
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda:f.read(8*1024*1024), b''): h.update(block)
    return h.hexdigest()
def ref(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': sha(path)}
def read(reference):
    assert sha(reference['path']) == reference['sha256'], reference
    return json.loads(Path(reference['path']).read_text())
def write(name, value):
    guard()
    p = OUT / name
    assert p.is_relative_to(OUT) and not p.exists(), str(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    return ref(p)
def git(*args):
    return subprocess.check_output(['git','--no-optional-locks','--no-replace-objects','-C',str(ROOT),*args],env={**os.environ,'GIT_NO_LAZY_FETCH':'1'})
def snapshot():
    names = ['research-state.yaml','research_config.yaml']
    names += [str(p.relative_to(ROOT)) for p in (ROOT/'data').glob('*') if p.is_file() and (p.suffix in ('.jsonl','.lock') or p.name == 'qd-ed-shared-resource-active.json')]
    session = ROOT/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z'
    names += [str(p.relative_to(ROOT)) for p in (session/'.coordinator').glob('*') if p.is_file()]
    names += [str(session.relative_to(ROOT)/'REPORT.md'),'docs/03_evidence/qd_ed_final/iteration-ledger.md']
    return {'head':git('rev-parse','HEAD').decode().strip(),'status':git('status','--porcelain').decode(),
            'files':{n:ref(ROOT/n) for n in names if (ROOT/n).is_file()}}
def check(name, fn):
    guard(); t=time.monotonic()
    try:
        value=fn(); CHECKS[name]={'status':'PASS','seconds':time.monotonic()-t}
        print(name,'PASS',flush=True);return value
    except BaseException as e:
        CHECKS[name]={'status':'FAIL','error':repr(e),'seconds':time.monotonic()-t}
        raise

def main():
    guard();os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:2])
    a=read(ref(OUT/'authority-v1.json'))
    assert a['owner']==str(ROOT) and a['source']==SOURCE and a['output_directory']==str(OUT)
    read(a['authority']); adoption=read(a['adoption']); source_review=read(adoption['root_source_review'])
    assert git('rev-parse','HEAD').decode().strip()==SOURCE
    before=snapshot();write('preservation-before-v1.json',before)
    for r in adoption['unchanged_ledger_prefixes'].values():
        assert sha(r['path'])==r['sha256'] and Path(r['path']).stat().st_size==r['bytes']
    authority=read(adoption['adopted_authority']);read(adoption['adopted_amendment']);read(adoption['accounting_reused'])
    write('authority-verification-v1.json',{'authority':ref(OUT/'authority-v1.json'),'standing_authority':a['authority'],'adoption':a['adoption'],'root_source_review':adoption['root_source_review'],'source':SOURCE,'STOP_present':False,'started_at':STARTED,'CUDA_VISIBLE_DEVICES':'','cpu_affinity':sorted(os.sched_getaffinity(0)),'adopted_accounting_snapshot':adoption['retained_snapshot'],'adopted_authority':adoption['adopted_authority'],'adopted_amendment':adoption['adopted_amendment']})
    previous=read(ref(TURNS/'001219/runtime-input-repair/report-v1.json'))
    oldplan=read(previous['candidate'])
    readiness=read(ref(TURNS/'001223/runtime-readiness-review-v1.json'))
    oldruntime=read(readiness['runtime'])
    assert readiness['status']=='PASS_READINESS_ONLY_NOT_RELEASE'
    assert readiness['accounting_authority']==adoption['adopted_authority']
    read(readiness['reused_probe_review']);read(readiness['probe_terminal'])
    oldroot=oldruntime['worktree']
    def relocate(v):
        if isinstance(v,str):return v.replace(oldroot,str(ROOT))
        if isinstance(v,list):return [relocate(x) for x in v]
        if isinstance(v,dict):return {k:relocate(x) for k,x in v.items()}
        return v
    sys.path.insert(0,str(ROOT))
    from scripts import qd_ed_n36_bridge as b, qd_ed_n36_contract as c, qd_ed_n36_recovery as recovery
    from scripts import qd_ed_n36_build as native, qd_ed_n23_worker as w
    from scripts.qd_ed_n34_controller import verify_semantics
    from scripts.qd_ed_n36_prepare import prepare
    from scripts import qd_ed_available_gpu_queue as queue
    source=check('owning_source_strict_record',lambda:b.closure.source_record(ROOT,b.source_paths(ROOT)))
    write('source-record-v1.json',source)
    oldindex={x['path']:x['sha256'] for x in oldplan['source']['files']}
    newindex={x['path']:x['sha256'] for x in source['files']}
    delta=[{'path':p,'old_sha256':oldindex.get(p),'new_sha256':newindex.get(p)} for p in sorted(oldindex.keys()|newindex.keys()) if oldindex.get(p)!=newindex.get(p)]
    assert {x['path'] for x in delta}==set(source_review['changed_files']), delta
    assert git('diff','--name-only',oldplan['source']['commit'],SOURCE).decode().splitlines()==source_review['changed_files']
    write('source-delta-v1.json',{'review':adoption['root_source_review'],'old_commit':oldplan['source']['commit'],'new_commit':SOURCE,'delta':delta,'all_other_source_bytes_unchanged':True,'repair_tests_repeated':False})
    runtime=relocate(copy.deepcopy(oldruntime))
    # Preserve accepted readiness and every original field; historical preparation stays historical.
    runtime['preparation_history']=[copy.deepcopy(oldruntime['preparation'])]
    runtime['preparation']={'source':SOURCE,'release_enabled':False,'runtime_ready':True,'runtime_ready_scope':'Inherited turn1223 readiness only after unchanged-input verification; not new live evidence or release','status':'CPU_OWNER_REBIND','historical_runtime':readiness['runtime'],'readiness_review':ref(TURNS/'001223/runtime-readiness-review-v1.json'),'no_provider_or_device_probe':True}
    relocated_files=[]
    for old,row in zip(oldruntime['files'],runtime['files']):
        path=Path(row['path']);assert path.is_file(), str(path)
        assert '2026-08-10-eds-qd-stage-guidance-transition-design.md' not in str(path)
        if old['path']!=row['path']:
            row['resolved_path']=str(path.resolve())
            if 'link_target' in row:
                assert path.is_symlink() and os.readlink(path)==row['link_target']
            relocated_files.append({'old_path':old['path'],'new_path':row['path'],'sha256':row['sha256']})
    check('runtime_files_strict_all3291',lambda:b.runner.verify_files(runtime['files'],allowed_roots=(str(ROOT),runtime['artifact_root'])))
    assert runtime['tasks']==oldruntime['tasks'] and runtime['frozen_stage_provider']==oldruntime['frozen_stage_provider']
    check('stage_provider_contract',lambda:b.runner.stage_overrides(runtime))
    cli=runtime['frozen_stage_provider']; assert cli['model']=='gpt-6-astra' and cli['auth_mode']=='chatgpt'
    assert b.runner.digest(cli['cli_path'])==cli['cli_sha256']
    # Only already-accounted probe rows are decoded; no GPU or provider process is invoked.
    resource_id=runtime['cuda_egl_probe']['resource_id']
    resources=[json.loads(line) for line in (ROOT/'data/gpu-healthcheck-ledger.jsonl').read_text().splitlines() if resource_id in line]
    def reusable():
        result=queue.reusable_probe(runtime,runtime['gpu_mapping'],resources,root=ROOT)
        assert result==runtime['cuda_egl_probe'];return result
    check('historical_accounted_probe_static_reuse',reusable)
    probe_ref={'path':runtime['cuda_egl_probe']['evidence_path'],'sha256':runtime['cuda_egl_probe']['evidence_sha256']}
    probe=read(probe_ref)
    write('unchanged-inputs-v1.json',{'runtime_base':readiness['runtime'],'readiness_review':ref(TURNS/'001223/runtime-readiness-review-v1.json'),'file_count':len(runtime['files']),'relocated_files':relocated_files,'all_file_bytes_unchanged':True,'tasks_unchanged':True,'provider_contract_unchanged':True,'provider_cli':{'path':cli['cli_path'],'sha256':cli['cli_sha256']},'provider_login_rechecked':False,'probe':probe_ref,'probe_frame':ref(Path(probe_ref['path']).parent/'probe-frame.png'),'probe_source':ref(ROOT/'scripts/qd_ed_gpu_probe.py'),'probe_terminal':readiness['probe_terminal'],'live_device_evidence_created':False,'materialization_required':False})
    rr=write('runtime.owner-ready-v1.json',runtime)
    closure=read(previous['runtime_closure']);closure['runtime']=rr
    cr=write('runtime-closure.owner-v1.json',closure)
    check('runtime_closure_strict',lambda:b.closure.verify_runtime(closure,rr))
    proof=read(previous['controller_semantics'])
    for key,evref in list(proof['review_evidence'].items()):
        ev=read(evref)
        for row in ev['sources']:
            assert sha(row['path'])==row['sha256']
            row['path']=relocate(row['path']);assert sha(row['path'])==row['sha256']
        ev.update(runtime=rr,rebound_from=evref,source_commit=SOURCE,binding_review='Preserved source-review findings for byte-identical sources, rebound to adopted owning checkout. No independent production approval or live execution evidence created.')
        proof['review_evidence'][key]=write('controller-'+key+'.owner-v1.json',ev)
    proof.update(runtime=rr,rebound_from=previous['controller_semantics'],scope='Inherited ROOT_REVIEWED controller source semantics, source bytes reverified unchanged. Owning runtime binding is prospective and awaits independent final production review. No physical gain or live instance certified.')
    pr=write('controller-semantics.owner-v1.json',proof)
    check('controller_semantics_strict',lambda:verify_semantics(pr,rr,closure))
    native_ref={'path':str(TURNS/'001203/recovery-preparation/native-build-n36r1.draft-v1.json'),'sha256':previous['native_build']['sha256']}
    nv=read(native_ref)
    check('native_build_strict',lambda:native.manifest(native_ref))
    write('native-binding-provenance-v1.json',{'native_build':native_ref,'turn1219_native_build':previous['native_build'],'exact_value_unchanged':nv==read(previous['native_build']),'libraries':len(nv['libraries']),'same_worker_native_attestation_performed':False,'native_readiness':False})
    protocol_ref=oldplan['protocol'];read(protocol_ref)
    metadata={k:oldplan[k] for k in ('run_name','input_contract_label','attempt_identity')}
    for kind,filename in [('runtime_inventory','runtime-inventory.json'),('seed_plan','frozen-seed-plan.json')]:
        path=ROOT/'data'/filename;assert sha(path)==oldplan[kind+'_sha256']
        metadata[kind+'_path']=str(path);metadata[kind+'_sha256']=oldplan[kind+'_sha256']
    plan=check('prepare_all40',lambda:prepare(OUT/'draft',rr,runtime_closure_ref=cr,controller_semantics_ref=pr,native_build_ref=native_ref,root=ROOT,recovery_protocol_ref=protocol_ref))
    plan.update(metadata,runtime_ready=True,root_approval_granted=False,readiness_scope='Inherited turn1223 readiness; byte-verified owning rebind. No current live-device claim; not release authority.')
    check('metadata_complete_draft',lambda:c.validate_draft(plan))
    check('protocol_accounting_strict',lambda:recovery.validate_protocol(plan))
    check('adopted_authority_exact_refs',lambda:recovery.validate_authority(plan,authority))
    check('source_strict_reverification',lambda:b.verify_sources(plan))
    check('loaded_source_owner_binding',lambda:b.attest_loaded(ROOT,plan['source']))
    check('runtime_inputs_strict',lambda:b.runner.validate_runtime_inputs(plan,runtime,b.profiles(ROOT),ROOT,{'artifacts':runtime['artifact_root']}))
    fingerprints={str(Path(x['path']).resolve()) for x in runtime['files']}
    for task in runtime['tasks'].values():
        actual={str(p.resolve()) for p in Path(task['cache_dir']).rglob('*') if p.is_file()}
        assert actual and actual<=fingerprints
    rows=[]
    for row in plan['episodes']:
        m=check('manifest_'+row['episode_key'],lambda row=row:b._verify_manifest_bound(plan['expected_manifests'][row['episode_key']],plan,runtime,row))
        previous_m=read(oldplan['expected_manifests'][row['episode_key']])
        oldconfig=copy.deepcopy(previous_m['resolved_config']); newconfig=copy.deepcopy(m['resolved_config'])
        for config in (oldconfig,newconfig):
            for k in ('n34_runtime_binding','n36_runtime_binding'):
                if config.get(k):config[k]['source_commit']='<adopted-source-binding>'
        assert oldconfig==newconfig and row==previous_m['row'], 'scientific configuration drift'
        rows.append({'episode_key':row['episode_key'],'profile':row['profile'],'manifest':plan['expected_manifests'][row['episode_key']],'composed_config_sha256':m['composed_config_sha256'],'scientific_config_unchanged_except_source_binding':True})
    assert plan['episodes']==oldplan['episodes']
    planref=write('draft/plan.metadata-complete.draft.json',plan)
    write('all40-composition-v1.json',{'expected':40,'actual':len(rows),'all_pass':len(rows)==40,'rows':rows,'task_seed_arm_order_unchanged':True})
    write('adopted-accounting-bindings-v1.json',{'plan':planref,'authority':adoption['adopted_authority'],'accounting':plan['accounting'],'amendment':adoption['adopted_amendment'],'protocol':plan['protocol'],'protocol_review':plan['protocol_review'],'root_adoption':a['adoption'],'draft_authority_is_null_by_strict_contract':True,'adopted_snapshot':adoption['retained_snapshot'],'retained_margin_gpu_hours':adoption['retained_margin_gpu_hours'],'conservative_charge_gpu_hours':adoption['conservative_charge_gpu_hours'],'accounting_recomputed':False})
    events=[json.loads(line) for line in (ROOT/'data/attempt-ledger.jsonl').read_text().splitlines() if 'n36_dev_t00_c0_001147' in line]
    check('original_aborted_charge_preserved',lambda:recovery.preserve_charge(events))
    after=snapshot();assert before==after,'owner state/source status changed during composition'
    write('preservation-after-v1.json',{'snapshot':after,'equals_before':True,'source_strict_unchanged':True,'STOP_present':os.path.lexists(STOP),'elapsed_seconds':time.monotonic()-START})
    write('checks-v1.json',CHECKS)
    write('composition-result-v1.json',{'status':'PASS_CPU_OWNER_BOUND_ALL40_DISABLED','plan':planref,'runtime':rr,'runtime_closure':cr,'controller_semantics':pr,'native_build':native_ref,'source':SOURCE,'release_enabled':False,'frozen':False,'inherited_readiness_preserved':True,'native_readiness':False,'scientific_success':False,'target_met':False,'started_at':STARTED,'elapsed_seconds':time.monotonic()-START})

if __name__=='__main__':
    try:main()
    except BaseException as exc:
        # Retain failure without editing source or relaxing validators.
        p=OUT/'composition-failure-v1.json'
        if not p.exists():p.write_text(json.dumps({'error':repr(exc),'traceback':traceback.format_exc(),'checks':CHECKS},indent=2)+'\n')
        raise
