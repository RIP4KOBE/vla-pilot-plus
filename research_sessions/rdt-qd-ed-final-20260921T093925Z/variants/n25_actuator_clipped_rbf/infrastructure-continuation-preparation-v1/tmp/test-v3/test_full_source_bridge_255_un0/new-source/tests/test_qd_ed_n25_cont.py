import copy
import json
from pathlib import Path
import types
import pytest
from scripts import qd_ed_n25_cont_evidence as e,qd_ed_n25_cont_seal as sealmod,qd_ed_n25_cont_contract as c
from scripts import qd_ed_n25_cont_bridge as bridge,qd_ed_n25_cont_prepare as prepare,qd_ed_n25_cont_report as report,qd_ed_n25_cont_supervise as sup
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n25_contract as old
from n25_cont_fixtures import fixture,put,fake_cleanup,new_events

@pytest.fixture
def hist(tmp_path,monkeypatch):
    data,root,prior=fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(sealmod.subprocess,'check_output',lambda *a,**k:e.BASE+'\n')
    seal=sealmod.build(data,root,cleanup=fake_cleanup)
    monkeypatch.setattr(c,'SEAL',tmp_path/'seal.json');put(c.SEAL,seal)
    monkeypatch.setattr(c,'history',lambda **k:seal)
    return seal,prior,data,root


def test_complete_metadata_seal_no_tensor_or_stage_follow(hist):
    seal,_,_,_=hist
    assert len(seal['accepted_prefix'])==18 and len(seal['all_old_attempts'])==19
    assert seal['historical_unknowns']==e.UNKNOWN and seal['old_gpu_seconds']==e.OLD_SECONDS
    assert len(seal['accepted_prefix'][0]['evidence_index']['files'])==2100
    assert not any(Path(q['path']).suffix=='.pt' for q in seal['metadata_files'])
    assert not any('NEVER_READ' in q['path'] for q in seal['metadata_files'])
    assert sealmod.verify(seal,cleanup=fake_cleanup,check_cleanup=True)==seal

@pytest.mark.parametrize('fault',['attempt','event','outcome','reason','compute','wall','logical','complete','failed','usage','step','lifecycle','extra_error','success_usage','positions','projection_semantics','attestation','raw_response'])
def test_named_signature_fails_closed(hist,fault):
    seal,_,data,_=hist;final=copy.deepcopy(seal['all_old_attempts'][-1]['terminal']);public=json.loads(Path(data['references']['stage_public']['path']).read_text())
    edits={'attempt':('attempt_id','other'),'event':('event','aborted'),'outcome':('outcome_valid',True),'reason':('reason','Other'),
        'compute':('compute_outcome','aborted'),'wall':('gpu_process_wall_seconds',1800.),'logical':('provider_logical_call_attempts',44),
        'complete':('provider_completed_turns',38),'failed':('provider_failed_calls',7),'usage':('provider_usage_complete_calls',43)}
    if fault in edits:k,v=edits[fault];final[k]=v
    elif fault=='step':public['calls'][0]['global_step']=95
    elif fault=='lifecycle':public['calls'][0]['transport']['lifecycle']['first_completed_observed_at']=3.
    elif fault=='extra_error':public['calls'][0]['transport']['lifecycle']['events'].append({'kind':'x','error_category':'other'})
    elif fault=='success_usage':public['calls'][10]['codex_usage_complete_calls']=0
    elif fault=='positions':public['calls'][1]['event_position']=0
    elif fault=='projection_semantics':public['response_payloads_included']=True
    elif fault=='attestation':public['attestation']['all_logical_calls_included']=False
    else:public['calls'][0]['raw_response']=None
    with pytest.raises(ValueError):e.failed_signature(final,public)

@pytest.mark.parametrize('fault',['file_drift','late_audit','unknown_true','old_cost','missing_prefix','tensor_allow','unlisted_ref','byte_bound'])
def test_seal_inventory_and_unknown_negative(hist,fault,monkeypatch):
    seal,_,_,_=hist;seal=copy.deepcopy(seal)
    if fault=='file_drift':Path(seal['metadata_files'][0]['path']).write_text('{}')
    elif fault=='late_audit':Path(seal['failed_audits_absent'][0]['path']).write_text('{}')
    elif fault=='unknown_true':seal['historical_unknowns']['all_non_transport_gates_verified']=True
    elif fault=='old_cost':seal['old_gpu_seconds']=0
    elif fault=='missing_prefix':seal['accepted_prefix'].pop()
    elif fault=='tensor_allow':seal['metadata_files'].append({'path':'/tmp/unknown.pt','sha256':'x'})
    elif fault=='unlisted_ref':
        with pytest.raises(ValueError):e.Reader(seal['metadata_files']).json({'path':'/tmp/NEVER.json','sha256':'x'})
        return
    else:
        reader=e.Reader(seal['metadata_files']);reader.bytes=128*1024*1024
        with pytest.raises(ValueError):reader.read_bytes(seal['metadata_files'][0])
        return
    with pytest.raises(ValueError):sealmod.verify(seal)

@pytest.mark.parametrize('fault',['none','live','reused_pid','old_boot','orphan_session','owned_command'])
def test_public_process_identity_cleanup(tmp_path,fault):
    proc=tmp_path/'proc';(proc/'sys/kernel/random').mkdir(parents=True);(proc/'sys/kernel/random/boot_id').write_text('boot')
    def add(pid,ticks,session=0,cmd='other'):
        path=proc/str(pid);path.mkdir();fields=['S','1','0',str(session)]+['0']*15+[str(ticks)]
        (path/'stat').write_text(str(pid)+' (python) '+' '.join(fields));(path/'cmdline').write_text(cmd)
    p={'pid':999,'proc_start_ticks':'123','boot_id':'boot'}
    if fault=='live':add(999,123)
    elif fault=='reused_pid':add(999,456)
    elif fault=='old_boot':p['boot_id']='old';add(999,123)
    elif fault=='orphan_session':add(998,456,999)
    elif fault=='owned_command':add(998,456,cmd='python '+e.FAILED)
    if fault in {'live','orphan_session','owned_command'}:
        with pytest.raises(ValueError):e.process_cleanup([p],proc=proc)
    else:assert e.process_cleanup([p],proc=proc)['no_owned_processes']


def make_plan(hist):
    seal,prior,_,_=hist
    return prepare.build_plan(prior,seal,{'commit':'new','files':prior['code_files']})


def test_exact22_mapping_and_disabled_draft(hist):
    seal,prior,_,_=hist;plan=make_plan(hist)
    assert plan['frozen'] is False and plan['n25_infrastructure_continuation']['executable'] is False
    assert len(plan['episodes'])==22 and plan['episodes'][0]['retry_of']==e.FAILED
    assert [r['budget_bucket'] for r in plan['episodes']].count('baseline')==5
    assert [r['budget_bucket'] for r in plan['episodes']].count('development')==16
    assert [r['budget_bucket'] for r in plan['episodes']].count('recovery')==1
    for n,row in enumerate(plan['episodes'],18):
        assert all(row[k]==v for k,v in prior['episodes'][n].items() if k not in {'iteration','episode_key','budget_bucket'})
    assert not any(x['episode_key'] in {r['episode_key'] for r in prior['episodes'][:18]} for x in plan['episodes'])

@pytest.mark.parametrize('index,fault',[(0,'none'),(1,'none'),(0,'already_retried'),(0,'valid_prior'),(0,'other_attempt'),(1,'prior_suffix'),(0,'row_changed')])
def test_exact_cross_cohort_repeat_and_valid_import_rejection(hist,index,fault):
    seal,_,_,_=hist;plan=make_plan(hist);row=copy.deepcopy(plan['episodes'][index]);events=w.read_ref(seal['old_ledger'])
    if index==1:events+=new_events(plan,1)
    if fault=='already_retried':events+=new_events(plan,1)
    elif fault=='valid_prior':events[-1]['outcome_valid']=True
    elif fault=='other_attempt':row['retry_of']='other'
    elif fault=='prior_suffix':events+=new_events(plan,2)[3:]
    elif fault=='row_changed':row['policy_seed']+=1
    if fault=='none':c.check_retry(events,row,vars(r))
    else:
        with pytest.raises(ValueError):c.check_retry(events,row,vars(r))

@pytest.mark.parametrize('n,fail,wins,decision',[(22,None,5,'ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION'),(22,None,0,'REJECT'),(10,None,0,'REJECT_NUMERIC_FUTILITY'),(9,None,0,'INVALID_OR_INTERRUPTED'),(1,0,0,'INVALID_OR_INTERRUPTED'),(5,4,2,'INVALID_OR_INTERRUPTED')])
def test_logical_denominator_all_costs_and_unknowns(hist,n,fail,wins,decision):
    seal,_,_,_=hist;plan=make_plan(hist);events=new_events(plan,n,fail=fail,wins=wins)
    def accept(row,ev):
        g=[v for v in ev if v['episode_key']==row['episode_key']];final=g[-1]
        e.require(final['outcome_valid'],'invalid')
        return {'episode_key':row['episode_key'],'task_id':row['task_id'],'profile':row['profile'],'attempt_id':final['attempt_id'],'success':final['success']},{'guided_decisions':1,'parent_rounds_verified':10},{}
    result=report.analyze(plan,seal,events,accept)
    assert result['decision']==decision and result['dispatched']==19+n and len(result['attempts'])==19+n
    assert result['unknown_token_calls']==6 and result['all_attempt_token_usage_complete'] is False
    assert result['old_costs']['all_attempt_costs']['N23']['gpu_process_wall_seconds']['observed_total']>=e.FAILED_SECONDS
    assert result['audited_cells']==18+(fail if fail is not None else n)
    assert result['original_disposition']=='INVALID_OR_INTERRUPTED'

@pytest.mark.parametrize('fault',['none','baseline','development','recovery','attempts','local','cumulative','protected','inflight','old_drift'])
def test_all_capacity_gates(hist,monkeypatch,fault):
    seal,_,_,_=hist;events=w.read_ref(seal['old_ledger']);record={'remaining_local_gpu_hours':5.}
    snap={'running':0,'gpu_healthcheck_inflight':0,'gpu_hours_consumed':42.7,'gpu_hours_by_bucket':{'validation':10.,'formal':0.},
        'by_bucket':{'baseline':50,'development':183,'validation':60,'formal':0,'recovery':11},'dispatched':304}
    from scripts import qd_ed_n25_backend as backend
    monkeypatch.setattr(backend,'settled_proof',lambda *a:None)
    if fault in {'baseline','development','recovery'}:snap['by_bucket'][fault]=c.CAPS['buckets'][fault]
    elif fault=='attempts':snap['dispatched']=400
    elif fault=='local':record['remaining_local_gpu_hours']=.1
    elif fault=='cumulative':snap['gpu_hours_consumed']=80.
    elif fault=='protected':snap['gpu_hours_by_bucket']['validation']=0.;snap['gpu_hours_consumed']=60.
    elif fault=='inflight':snap['running']=1
    elif fault=='old_drift':events[-1]['outcome_valid']=True
    ns={**vars(r),'budget_snapshot':lambda *a:snap}
    if fault=='none':assert c.budget_check({},events,[],ns,record,dispatch=True)['remaining_slots']=={'baseline':5,'development':16,'recovery':1}
    else:
        with pytest.raises(ValueError):c.budget_check({},events,[],ns,record,dispatch=True)


def test_four_function_reverse_and_old_routing(monkeypatch):
    root=r.ROOT;index=json.loads((root/bridge.DOC/'reverse-routes-v1.json').read_text())
    for x in index['files']:
        lines=(root/x['path']).read_text().splitlines(keepends=True);new=''.join(lines)
        for y in reversed(x['edits']):lines[y['new_start']:y['new_end']]=y['old'].splitlines(keepends=True)
        restored=''.join(lines);assert e.hashlib.sha256(restored.encode()).hexdigest()==x['old_sha256']
        a,b=bridge.functions(restored),bridge.functions(new);assert set(a)==set(b)
        assert {k for k in a if a[k]!=b[k]}==bridge.ROUTES[x['path']]
    assert r.metered_support({'n25_cohort':{}}) is old
    assert r.metered_support({'n25_cohort':{},'n25_infrastructure_continuation':{}}) is c
    assert r.is_n25_plan({'n25_cohort':{},'n25_infrastructure_continuation':{}})

@pytest.mark.parametrize('fault',['none','profile','split','timeout','source','artifact','mode','gpu'])
def test_new_context_routes_without_old_history_replay(hist,monkeypatch,fault):
    seal,_,_,root=hist;plan=make_plan(hist);plan.update(frozen=True,n25_infrastructure_continuation={'schema':'n25-infrastructure-continuation-v1','protocol':{'sha256':c.PROTOCOL_SHA}})
    row=plan['episodes'][0];out=Path(plan['artifact_root']).resolve()/'attempts'/'new';context={'episode_key':row['episode_key'],'profile':row['profile'],
        'runtime':seal['runtime'],'source':{'commit':plan['source_commit'],'files':plan['code_files']},'attempt_id':'new'}
    runtime={'gpu_mapping':{'physical_gpu':7,'uuid':'fixed'}};monkeypatch.setattr(w,'verify_source',lambda *a:None)
    if fault=='profile':context['profile']='N26'
    elif fault=='split':row['split']='formal'
    elif fault=='timeout':row['timeout_seconds']=1900
    elif fault=='source':context['source']['commit']='bad'
    elif fault=='artifact':out=root/'escape'
    elif fault=='mode':plan['n25_cohort']['worker_audit']={}
    elif fault=='gpu':runtime['gpu_mapping']['physical_gpu']=3
    if fault=='none':assert c.validate_worker_context(context,[],root,out,plan,runtime)==(root,out,runtime)
    else:
        with pytest.raises(ValueError):c.validate_worker_context(context,[],root,out,plan,runtime)

@pytest.mark.parametrize('fail_index',[0,1,4])
def test_supervisor_never_recovers_new_invalid(hist,tmp_path,monkeypatch,fail_index):
    seal,_,_,_=hist;plan=make_plan(hist);out=tmp_path/'controller';monkeypatch.setattr(c,'RUN_DIR',out);status=out/'execution/supervisor-status-v1.json'
    path=tmp_path/'new-plan.json';put(path,plan);called=[];events=[]
    monkeypatch.setattr(sup.old_supervisor,'device_check',lambda:None)
    def one(path,plan,row):
        i=plan['episodes'].index(row);called.append(i);ev=new_events(plan,i+1,fail=fail_index);events[:]=ev;return ev[-1]
    monkeypatch.setattr(sup,'one_attempt',one);monkeypatch.setattr(r,'read_events',lambda p:events)
    monkeypatch.setattr(c,'accepted_cell',lambda p,row,ev,*a:[x for x in ev if x['episode_key']==row['episode_key']][-1])
    monkeypatch.setattr(old,'read_worker_report',lambda *a:{})
    monkeypatch.setattr(c.native,'from_output',lambda *a:({'guided_decisions':1,'parent_rounds_verified':10},{}))
    final=[];monkeypatch.setattr(report,'write_terminal',lambda *a:final.append(list(events)))
    original=one
    def with_output(*a):v=original(*a);v['output_dir']=str(tmp_path/'out');return v
    monkeypatch.setattr(sup,'one_attempt',with_output)
    with pytest.raises(ValueError):sup.execute(path,plan,status)
    assert called==list(range(fail_index+1)) and len(final)==1
    assert json.loads(status.read_text())['status']=='failed'

@pytest.mark.parametrize('fault',['interval','latency','order','event_types','item_types','event_time'])
def test_failed_lifecycle_observable_timing(hist,fault):
    seal,_,data,_=hist;public=json.loads(Path(data['references']['stage_public']['path']).read_text());x=public['calls'][0];life=x['transport']['lifecycle']
    if fault=='interval':life['timeout_observed_at']=179.
    elif fault=='latency':x['codex_call_latency_s']=179.
    elif fault=='order':life['cleanup_started_at']=190.
    elif fault=='event_types':x['transport']['event_types']=[]
    elif fault=='item_types':x['transport']['item_types']=[]
    else:life['events'][0]['observed_at']=-1.
    with pytest.raises(ValueError):e.failed_signature(seal['all_old_attempts'][-1]['terminal'],public)


def test_reader_rejects_oversize_before_allocating(tmp_path,monkeypatch):
    p=tmp_path/'big.json';p.write_text('{}');reader=e.Reader([e.ref(p)]);real=Path.stat
    def stat(q,*a,**k):
        if q==p:return types.SimpleNamespace(st_size=17*1024*1024,st_mode=0o100644)
        return real(q,*a,**k)
    monkeypatch.setattr(Path,'stat',stat)
    with pytest.raises(ValueError,match='before read'):reader.read_bytes(reader.records[str(p)])


def test_freeze_existing_plan_fail_early(tmp_path,monkeypatch):
    p=tmp_path/'plan.json';put(p,{'immutable':True});monkeypatch.setattr(c,'PLAN',p)
    with pytest.raises(ValueError,match='already exists'):prepare.freeze(p,root=tmp_path)
    assert json.loads(p.read_text())=={'immutable':True}

@pytest.mark.parametrize('fault',['none','timeout','popen','native'])
def test_original_run_plan_charges_and_cleans_under_new_route(hist,tmp_path,monkeypatch,fault):
    import contextlib,subprocess
    seal,_,_,_=hist;plan=make_plan(hist);plan['run_name']='synthetic';plan['n25_infrastructure_continuation']={'schema':'n25-infrastructure-continuation-v1'}
    plan['worktree']=str(tmp_path);path=tmp_path/'frozen.json';put(path,plan);row=plan['episodes'][0]
    runtime={'gpu_mapping':{'uuid':'fixed','egl_device_index':4},'environment':{},'frozen_stage_provider':{}}
    seen=[];terminals=[];deadline=[];clean=[]
    monkeypatch.setattr(r,'locked',lambda *a,**k:contextlib.nullcontext())
    monkeypatch.setattr(r,'validate_plan',lambda *a,**k:(plan,{'profiles':{row['profile']: {}}},runtime))
    monkeypatch.setattr(r,'read_events',lambda p:[]);monkeypatch.setattr(r,'read_state',lambda p:{})
    monkeypatch.setattr(r,'runtime_gpu',lambda *a:7);monkeypatch.setattr(r,'check_budget',lambda *a,**k:1800)
    monkeypatch.setattr(c,'check_retry',lambda *a:None);monkeypatch.setattr(c,'protected_budget',lambda *a,**k:None)
    monkeypatch.setattr(c,'admission',lambda *a:{'n25_continuation_id':c.COHORT})
    monkeypatch.setattr(r,'gpu_admission',lambda **k:{'physical_gpu':7});monkeypatch.setattr(r,'verify_provider',lambda *a,**k:None)
    monkeypatch.setattr(r,'child_environment',lambda *a:{})
    def command(p,m,rt,row,aid):return ['python',str(tmp_path/'main.py')],tmp_path/'output'/aid
    monkeypatch.setattr(r,'build_command',command);monkeypatch.setattr(w,'build_context',lambda *a:{'synthetic':True})
    def append(root,event):seen.append(event['event']);terminals.append(event)
    monkeypatch.setattr(r,'append_event',append)
    def popen(*a,**k):
        assert seen==['reserved','dispatched']
        if fault=='popen':raise OSError('synthetic launch failure')
        return types.SimpleNamespace(pid=999999999)
    monkeypatch.setattr(r.subprocess,'Popen',popen)
    original_read=Path.read_text
    def public_process_read(path,*a,**k):
        if str(path)=='/proc/999999999/stat':raise FileNotFoundError('synthetic process has no host PID')
        return original_read(path,*a,**k)
    monkeypatch.setattr(Path,'read_text',public_process_read)
    def wait(proc,seconds,**k):
        deadline.append(seconds)
        if fault=='timeout':raise subprocess.TimeoutExpired('synthetic',seconds)
        return 0
    monkeypatch.setattr(r,'wait_exclusively',wait);monkeypatch.setattr(r,'terminate_owned',lambda p:clean.append(p))
    def audit(out,ns):
        if fault=='native':raise ValueError('synthetic native fault')
        put(Path(out)/'eds_eval/in-worker-audit-receipt.json',{'accepted':True});return {'evidence_complete':True}
    monkeypatch.setattr(c,'read_worker_report',audit)
    monkeypatch.setattr(r,'validate_result',lambda *a:{'outcome_valid':True,'success':False})
    monkeypatch.setattr(r,'failed_outcome',lambda *a,**k:('aborted',{'outcome_valid':False,'failure_class':fault}))
    with c.supervised_scope(plan,tmp_path,row['episode_key']):
        if fault=='none':assert len(r.run_plan(path,split='dev',iteration=c.COHORT,episode_keys=[row['episode_key']],root=tmp_path))==1
        else:
            with pytest.raises(r.GateError):r.run_plan(path,split='dev',iteration=c.COHORT,episode_keys=[row['episode_key']],root=tmp_path)
    assert len(clean)==1 and seen[:2]==['reserved','dispatched'] and seen[-1] in r.TERMINAL
    assert terminals[-1]['gpu_process_wall_seconds']>=0 and terminals[-1]['n25_episode_dispatched'] is True
    if fault!='popen':assert deadline==[1800]

@pytest.mark.parametrize('fault',['missing_status','lagging_status','failed_after_valid','normal_invalid'])
def test_report_preserves_valid_journal_prefix_and_cost_after_status_failure(hist,tmp_path,monkeypatch,fault):
    seal,_,_,_=hist;plan=make_plan(hist);planpath=tmp_path/'plan-report.json';put(planpath,plan)
    run=tmp_path/'variant-control';monkeypatch.setattr(c,'RUN_DIR',run);status=run/'execution/supervisor-status-v1.json'
    ev=new_events(plan,1,fail=0 if fault=='normal_invalid' else None);out=tmp_path/'native'
    for name in ('attempt-result.json','n23-worker-context.json','eds_eval/decision-evidence-audit.json','eds_eval/in-worker-audit-receipt.json'):put(out/name,{'synthetic':True})
    for q in ev:q['output_dir']=str(out)
    def accepted(p,row,events,*a):
        final=events[-1];e.require(final['outcome_valid'],'invalid');return final
    monkeypatch.setattr(c,'accepted_cell',accepted);monkeypatch.setattr(old,'read_worker_report',lambda *a:{})
    monkeypatch.setattr(c.native,'from_output',lambda *a:({'guided_decisions':1,'parent_rounds_verified':10},{}))
    if fault!='missing_status':put(status,{'status':'failed','completed_keys':[] if fault!='failed_after_valid' else [plan['episodes'][0]['episode_key']],'dev_gate_promoted':False})
    monkeypatch.setattr(c,'BRIDGE',tmp_path/'bridge.json');put(c.BRIDGE,{'synthetic':True})
    value=report.write_terminal(planpath,plan,status,tmp_path,{**vars(r),'read_events':lambda p:ev})
    assert value['decision']=='INVALID_OR_INTERRUPTED' and value['audited_cells']==(18 if fault=='normal_invalid' else 19)
    assert len(value['attempts'])==20 and value['dispatched']==20
    assert value['controller_evidence']['journal_accepted_keys']==([] if fault=='normal_invalid' else [plan['episodes'][0]['episode_key']])
    assert (run/'result-v1.json').exists() and (run/'execution/terminal-ledger-v1.json').exists()

@pytest.mark.parametrize('case',['promotion','reject','futility','invalid','status_disagreement','wrong_cost','wrong_disposition','drop_old','drop_marker','receipt_source','wrong_provider'])
def test_independent_existing_terminal_review(hist,tmp_path,monkeypatch,case):
    from n25_cont_fixtures import materialize_new
    from scripts import qd_ed_n25_cont_terminal as terminal
    seal,_,_,_=hist;plan=make_plan(hist);n=22 if case in {'promotion','reject','wrong_disposition'} else 10 if case=='futility' else 2
    fail=1 if case=='invalid' else None;events=new_events(plan,n,fail=fail,wins=0 if case in {'reject','futility'} else 5)
    pref,source,cells=materialize_new(tmp_path,plan,seal,events)
    def accept(row,ev):
        final=next(g[-1] for g in e.groups(ev).values() if g[0]['episode_key']==row['episode_key']);e.require(final['outcome_valid'],'invalid')
        return cells[row['episode_key']]
    result=report.analyze(plan,seal,events,accept);snapshot=put(tmp_path/'new-ledger.json',events)
    phase='completed_all_forty_audited' if n==22 else 'rejected_numeric_futility' if case=='futility' else 'failed'
    prefix=[x['episode_key'] for x in result['accepted_cells'][18:]]
    status={'status':phase,'completed_keys':prefix,'dev_gate_promoted':result['dev_gate_promoted']}
    consistent=True
    if case=='status_disagreement':status['completed_keys']=[];consistent=False;result['journal_reconstructed_disposition']=result['decision'];result['decision']='INVALID_OR_INTERRUPTED';result['dev_gate_promoted']=False
    sr=put(tmp_path/'new-status.json',status);result.update(plan=pref,ledger_snapshot=snapshot,terminal_status={**sr,'content':status},
        controller_evidence={'consistent':consistent,'completed_keys':status['completed_keys'],'journal_accepted_keys':prefix,'status_phase':phase})
    if case=='wrong_cost':result['all_attempt_costs']['N23']['gpu_process_wall_seconds']['observed_total']+=1
    elif case=='wrong_disposition':result['decision']='REJECT'
    elif case=='drop_old':result['attempts'].pop(18)
    elif case=='drop_marker':
        q=cells[plan['episodes'][1]['episode_key']][0]['audit'];v=json.loads(Path(q['path']).read_text());v.pop('n25_actuator_clipped_rbf_audit');Path(q['path']).write_text(json.dumps(v))
    elif case=='receipt_source':
        q=cells[plan['episodes'][0]['episode_key']][0]['worker_receipt'];v=json.loads(Path(q['path']).read_text());v['source']['commit']='bad';Path(q['path']).write_text(json.dumps(v))
    elif case=='wrong_provider':
        # Mutate public receipt-bound terminal, retaining original reference: hash rejection.
        q=cells[plan['episodes'][0]['episode_key']][0]['attempt_result'];v=json.loads(Path(q['path']).read_text());v['stage_transport']['backend']='poe';Path(q['path']).write_text(json.dumps(v))
    reader=e.Reader(terminal.metadata_inventory(result))
    if case in {'wrong_cost','wrong_disposition','drop_old','drop_marker','receipt_source','wrong_provider'}:
        with pytest.raises(ValueError):terminal.review_existing(result,plan,seal,events,reader,source,cleanup=fake_cleanup)
    else:
        value=terminal.review_existing(result,plan,seal,events,reader,source,cleanup=fake_cleanup)
        assert value['cohort_disposition']==result['decision'] and value['tensor_reads']==0

@pytest.mark.parametrize('fault',['none','science','route','unlisted','manifest'])
def test_full_source_bridge_255_unchanged_and_exact_routes(tmp_path,monkeypatch,fault):
    import shutil
    root=r.ROOT;paths=bridge.source_paths(root);copyroot=tmp_path/'new-source'
    for p in paths:
        target=copyroot/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((root/p).read_bytes())
    original=w.read_ref(e.ref(root/bridge.DOC/'original-source-v1.json'))
    seal={'original_source':original,'historical_backend_proof':{'path':'/synthetic/old-proof.json','sha256':'old'}}
    source={'commit':'new','files':[{'path':p,'sha256':e.sha(copyroot/p)} for p in sorted(paths)]}
    source['sha256']=e.canonical(source['files'])
    changes=bridge.EXTRAS|set(bridge.ROUTES)
    if fault=='science':(copyroot/'core/rdt_policy_steer.py').write_text('altered')
    elif fault=='route':(copyroot/'scripts/qd_ed_n23_worker.py').write_text('altered')
    elif fault=='unlisted':changes=changes|{'other.py'}
    elif fault=='manifest':source['files'].pop()
    monkeypatch.setattr(bridge.subprocess,'check_output',lambda *a,**k:'\n'.join(sorted(changes)))
    if fault=='none':
        value=bridge.build(source,seal,copyroot);assert len(value['same_files'])==255 and value['new_numerical_preflight'] is False
    else:
        with pytest.raises(ValueError):bridge.build(source,seal,copyroot)

@pytest.mark.parametrize('fault',['no_authority','bad_state_ref','raised_attempts','raised_hours','protected_reduced','gpu','hold','parallel'])
def test_adopted_finite_state_failclosed(hist,monkeypatch,fault):
    seal,_,_,_=hist
    rec={'existing_budget_authority':{'path':'/synthetic/budget.json','sha256':'x'},'source':{},'runtime':{}}
    state={'n25_continuation_authority':{'path':'/synthetic/authority.json','sha256':'a'},'n25_budget_authority':rec['existing_budget_authority'],
        'budget':{'max_episode_attempts':494,'max_gpu_hours':100.,'reserved':copy.deepcopy(c.CAPS['buckets']),
            'gpu_hour_reservations':copy.deepcopy(c.CAPS['protected_gpu_hours']),'amendment':'exact'},
        'resource_isolation':{'status':'ACTIVE','validation_status':'PASS','private_budget':True},'max_concurrent_gpu_workers':1}
    def read(q):
        if fault=='no_authority':raise FileNotFoundError('authority absent')
        return {'amendment':'exact'} if q==rec['existing_budget_authority'] else rec
    monkeypatch.setattr(w,'read_ref',read);monkeypatch.setattr(c,'ref',lambda p:state['n25_continuation_authority'])
    def authority(*a):
        if fault=='bad_state_ref':raise ValueError('not adopted')
    monkeypatch.setattr(c,'authority',authority)
    if fault=='raised_attempts':state['budget']['max_episode_attempts']=495
    elif fault=='raised_hours':state['budget']['max_gpu_hours']=101.
    elif fault=='protected_reduced':state['budget']['gpu_hour_reservations']['formal']=0
    elif fault=='hold':state['external_resource_hold']={'do_not_auto_resume':True}
    elif fault=='parallel':state['max_concurrent_gpu_workers']=2
    ns={**vars(r),'authorized_gpu':lambda s:3 if fault=='gpu' else 7}
    with pytest.raises((ValueError,FileNotFoundError)):c.require_state(state,ns)
