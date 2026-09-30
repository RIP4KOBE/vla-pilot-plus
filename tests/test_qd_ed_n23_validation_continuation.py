"""Synthetic historical continuation provenance, no live output/state reads."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from test_qd_ed_n23_validation import write,events_for,seeds,no_cuda
from scripts import qd_ed_final_runner as r
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n23_v2_contract as dev
from scripts import qd_ed_n23_v2_supervise as sup
from scripts import qd_ed_n23_validation_contract as c
from scripts import qd_ed_n23_validation_continuation as h
from scripts import qd_ed_n23_historical_n7_metrics_adapter as adapter
from core.eds_eval_metrics import EDSChunkMetrics


@pytest.fixture
def history(tmp_path,monkeypatch):
    # Actual schema and three-row identity; all evidence is synthesized below basetemp.
    for name in ('ADDENDUM','MANIFEST','SOURCE_REVIEW','AUTHORITY','ROOT_REVIEW','FAILURE','EXCEPTION','ORIGINAL_WRITER','STATUS','SEAL','SNAPSHOT'):
        monkeypatch.setattr(h,name,tmp_path/(name+'.json'))
    monkeypatch.setattr(h,'EXTERNAL_ROOT',tmp_path/'external')
    monkeypatch.setattr(c,'DEV_PLAN',tmp_path/'dev-plan.json');monkeypatch.setattr(c,'DEV_RESULT',tmp_path/'result.json')
    for name in ('ADDENDUM','ROOT_REVIEW','EXCEPTION','ORIGINAL_WRITER'):
        write(getattr(h,name),{'synthetic':name});monkeypatch.setattr(h,name+'_SHA',w.sha(getattr(h,name)))
    rows=[{**v,'iteration':dev.COHORT,'split':'dev','seed_block':'dev','budget_bucket':'baseline' if a=='C0' else 'development',
        'profile':a,'episode_key':f'dev{v["task_id"]}{a}'} for v in seeds()['blocks']['dev'] for a in dev.ARMS]
    runtime=write(tmp_path/'runtime.json',{})
    parent={'source_commit':c.DEV_COMMIT,'code_files':[],'worktree':str(tmp_path/'later-evaluation-root'),
        'episodes':rows,'runtime_manifest_path':runtime['path'],'runtime_manifest_sha256':runtime['sha256'],
        'n23_cohort':{'backend_proof':{'old':'metered-backend'}}}
    write(c.DEV_PLAN,parent)
    files=[];committed={}
    for relative in sorted(h.FILES):
        data=Path(adapter.__file__).read_bytes() if relative=='continuation/n23_n7_metrics_adapter.py' else (relative+'\n').encode()
        p=h.EXTERNAL_ROOT/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        committed[relative]=data;files.append({'path':relative,'sha256':w.sha(p)})
    source={'root':str(h.EXTERNAL_ROOT),'commit':h.EXTERNAL_COMMIT,'files':files,'sha256':w.canonical_sha(files),
        'imported_writer':h.ref(h.ORIGINAL_WRITER)}
    write(h.MANIFEST,source)
    commands=[]
    def git(argv,**kw):
        commands.append(argv)
        assert argv[:2]==['git','show'] and kw['cwd']==h.EXTERNAL_ROOT
        commit,name=argv[2].split(':',1);assert commit==h.EXTERNAL_COMMIT
        return committed[name]
    monkeypatch.setattr(h.subprocess,'check_output',git)
    events=[];entries=[];priors=[]
    for row,aid in zip(rows,h.PREFIX_IDS):
        group=events_for(row,aid=aid);final=group[-1];out=tmp_path/'attempts'/aid
        final['output_dir']=str(out);events+=group
        references={k:write(out/name,final if k=='attempt_result' else {}) for k,name in [
            ('attempt_result','attempt-result.json'),('audit','eds_eval/decision-evidence-audit.json'),
            ('worker_receipt','eds_eval/in-worker-audit-receipt.json'),('worker_context','n23-worker-context.json')]}
        metrics=write(out/'eds_eval/eds_metrics.jsonl',[],True)
        entries.append({'episode_key':row['episode_key'],'task_id':row['task_id'],'profile':row['profile'],
            'attempt_id':aid,'success':False,**references})
        priors.append({'episode_key':row['episode_key'],'attempt_id':aid,'success':False,'outcome_valid':True,
            'gpu_process_wall_seconds':1.,'terminal':references['attempt_result'],'metrics':metrics,
            'native_report':references['audit'],'native_receipt':references['worker_receipt']})
    failure={'schema':'n23-dev-legacy-metric-reader-failure-v1','original_source_commit':c.DEV_COMMIT,
        'original_plan':h.ref(c.DEV_PLAN),'prefix':priors,
        'original_failed_status':write(tmp_path/'old-status.json',{'status':'failed','completed_keys':['one','two'],'attempts':[1,2,3]}),
        'original_failed_result':write(tmp_path/'old-result.json',{'decision':'INVALID_OR_INTERRUPTED','audited_cells':2,'dispatched':3}),
        'original_dev_snapshot':write(tmp_path/'old-snapshot.jsonl',events,True)}
    for key in ('original_supervisor_log','source_serializer','source_checker'):
        failure[key]=write(tmp_path/(key+'.json'),{})
    write(h.FAILURE,failure);write(h.SNAPSHOT,events,True)
    review={'schema':'n23-continuation-source-review-v1','decision':'PASS_PREPARATION',
        'exception':h.ref(h.EXCEPTION),'failure_review':h.ref(h.FAILURE),'plan':h.ref(c.DEV_PLAN),'external_source':source,
        'owning_source':{'commit':c.DEV_COMMIT,'files':[],'sha256':w.canonical_sha([])},'runtime':runtime,
        'backend_proof':parent['n23_cohort']['backend_proof'],'cohort_id':dev.COHORT,'prefix_attempt_ids':list(h.PREFIX_IDS),
        'pending_keys':[v['episode_key'] for v in rows[3:]],'limits':dev.LIMITS,'validation_authorized':False,'formal_authorized':False}
    write(h.SOURCE_REVIEW,review)
    auth={'schema':'n23-legacy-metric-continuation-authority-v1','source_review':h.ref(h.SOURCE_REVIEW),
        'exception':h.ref(h.EXCEPTION),'failure_review':h.ref(h.FAILURE),'plan':h.ref(c.DEV_PLAN),
        'status_path':str(h.STATUS),'launch_seal_path':str(h.SEAL),'result_path':str(c.DEV_RESULT),
        'cohort_id':dev.COHORT,'initial_prefix_attempt_ids':list(h.PREFIX_IDS),'pending_keys':review['pending_keys'],'limits':dev.LIMITS,
        'initial_launches':1,'scientific_source_unchanged':True,'backend_preflight_authorized':False,
        'validation_authorized':False,'formal_authorized':False,
        'authority_interpretation':'prospective bounded coordinator engineering exception under continuing autonomous user instruction',
        'user_message':'继续完成满足目标且无需我介入的autoresearch'}
    write(h.AUTHORITY,auth)
    seal={'schema':'n23-continuation-launch-seal-v1','authority':h.ref(h.AUTHORITY),
        'process':{'pid':123,'proc_start_ticks':'1234','boot_id':'different-old-boot'},
        'prefix_attempt_ids':list(h.PREFIX_IDS),'pending_keys':review['pending_keys']}
    write(h.SEAL,seal)
    provenance={'authority':h.ref(h.AUTHORITY),'launch_seal':h.ref(h.SEAL),'original_failed_review':h.ref(h.FAILURE),
        'original_source_commit':c.DEV_COMMIT,'original_plan':h.ref(c.DEV_PLAN),'external_source':source,'imported_writer':h.ref(h.ORIGINAL_WRITER)}
    status={'continuation':provenance};write(h.STATUS,status)
    root_review={'dev_status':h.ref(h.STATUS)}
    result={'continuation':copy.deepcopy(provenance),'ledger_snapshot':h.ref(h.SNAPSHOT),
        'original_v2_disposition':'INVALID_OR_INTERRUPTED','original_v2_record_preserved':True,
        'original_failed_result':failure['original_failed_result'],'accepted_cells':entries}
    for name in ('MANIFEST','SOURCE_REVIEW','AUTHORITY','FAILURE'):
        monkeypatch.setattr(h,name+'_SHA',w.sha(getattr(h,name)))
    return SimpleNamespace(parent=parent,source=source,status=status,result=result,review=root_review,
        source_review=review,authority=auth,seal=seal,failure=failure,events=events,commands=commands)


@pytest.mark.parametrize('fault',['none','manifest','external_byte','external_git','adapter','source_review','authority','root_review',
    'old_status','old_result','source_provenance','authority_provenance','seal','plan','snapshot','old_failure_link','relabeled'])
def test_historical_provenance_preserves_original_failure_without_current_head(history,tmp_path,monkeypatch,fault):
    f=history
    if fault in {'manifest','source_review','authority','root_review'}:
        path=getattr(h,{'manifest':'MANIFEST','source_review':'SOURCE_REVIEW','authority':'AUTHORITY','root_review':'ROOT_REVIEW'}[fault]);path.write_text('{}')
    if fault=='external_byte':(h.EXTERNAL_ROOT/'continuation/n23_continuation_supervise.py').write_text('changed')
    if fault=='external_git':monkeypatch.setattr(h.subprocess,'check_output',lambda *args,**kw:b'changed committed bytes')
    if fault=='adapter':monkeypatch.setattr(h,'ADAPTER_SHA','other')
    if fault=='old_status':Path(f.failure['original_failed_status']['path']).write_text('{}')
    if fault=='old_result':Path(f.failure['original_failed_result']['path']).write_text('{}')
    if fault=='source_provenance':f.result['continuation']['external_source']={}
    if fault=='authority_provenance':f.result['continuation']['authority']={}
    if fault=='seal':f.result['continuation']['launch_seal']={}
    if fault=='plan':f.parent['source_commit']='later-evaluation-commit'
    if fault=='snapshot':f.result['ledger_snapshot']={}
    if fault=='old_failure_link':f.result['original_failed_result']={}
    if fault=='relabeled':f.result['original_v2_disposition']='REJECT'
    if fault=='none':
        assert h.provenance(f.parent,f.review,f.status,f.result)==f.failure
        assert len(f.commands)==8 and all(cmd[1]=='show' and cmd[2].startswith(h.EXTERNAL_COMMIT+':') for cmd in f.commands)
        # No live source HEAD/process/private authority gate is called for historical evidence.
        assert not f.parent['worktree'].endswith('study_worktree')
    else:
        with pytest.raises((ValueError,KeyError)):h.provenance(f.parent,f.review,f.status,f.result)


@pytest.mark.parametrize('fault',['none','cost','success','retry','id','metrics','receipt','order','snapshot'])
def test_three_original_valid_failures_are_not_reclassified(history,fault):
    f=history;entry=f.result['accepted_cells'][2];final=f.events[-1]
    if fault=='cost':final['gpu_process_wall_seconds']=2.
    if fault=='success':entry['success']=True
    if fault=='retry':f.events[-3]['retry_of']='other'
    if fault=='id':entry['attempt_id']='other'
    if fault=='metrics':Path(f.failure['prefix'][2]['metrics']['path']).write_text('changed')
    if fault=='receipt':entry['worker_receipt']={}
    if fault=='order':f.events[:6]=f.events[3:6]+f.events[:3]
    if fault=='snapshot':Path(f.failure['original_dev_snapshot']['path']).write_text('')
    if fault=='none':h.prefix(f.parent,f.failure,f.events,f.result,vars(r))
    else:
        with pytest.raises((ValueError,r.GateError)):h.prefix(f.parent,f.failure,f.events,f.result,vars(r))


@pytest.mark.parametrize('mode',['omitted','provider',None,'wrong','actuator_clipped_provider_v1'])
def test_exact_copied_n7_adapter_real_serializer_at_evaluation_head(tmp_path,mode):
    assert w.sha(adapter.__file__)==h.ADAPTER_SHA
    root=Path(r.ROOT);candidate=root/'configs/qd_ed_final/candidate_n7.json'
    parent={'worktree':str(root),'candidate_profiles':{'N7':{'path':str(candidate),'sha256':w.sha(candidate)}}}
    manifest=r.read_json(root/'configs/qd_ed_final/baseline_profiles.json')
    manifest['profiles']['N7']=r.expand_candidate('N7',r.read_json(candidate),manifest['profiles']['Q0'])
    metric=EDSChunkMetrics(qd_quality_mode='provider',qd_archive_active_for_chunk=True,
        score_call_count=11,search_evaluation_count=176,resample_count=10,renoise_count=10,rollout_count=10).to_jsonable()
    assert 'qd_quality_mode' not in metric
    if mode!='omitted':metric['qd_quality_mode']=mode
    write(tmp_path/'eds_eval/eds_metrics.jsonl',[metric],True)
    record={'dtype':'torch.bfloat16','shape':[16],'sha256':'a'*64,'values':[0.]*16}
    gate={'schema':'n5-native-grasp-timing-audit-v1','checked_decisions':1,'parent_rounds_verified':10,
        'canonical_batches_verified':11,'canonical_candidates_verified':176,'decisions':[{
            'terminal_raw_provider_quality':record,'terminal_native_costs':record,'selected_index':0,'selected_raw_reward':0.,'selected_cost':0.}]}
    report={'accepted':True,'evidence_complete':True,'n5_grasp_timing_audit':gate}
    args=({'guided_chunks':1,'output_dir':str(tmp_path)},{'profile':'N7'},report)
    kwargs=dict(parent=parent,root=root,r=vars(r),manifest=manifest)
    if mode in {'omitted','provider'}:
        assert h.native_counts(*args,**kwargs)[0]=={'guided_decisions':1,'parent_rounds_verified':10}
    else:
        with pytest.raises(ValueError):h.native_counts(*args,**kwargs)


def test_addendum_cannot_drift(tmp_path,monkeypatch):
    path=tmp_path/'addendum.md';path.write_text('different');monkeypatch.setattr(h,'ADDENDUM',path)
    with pytest.raises(ValueError):h.addendum()
