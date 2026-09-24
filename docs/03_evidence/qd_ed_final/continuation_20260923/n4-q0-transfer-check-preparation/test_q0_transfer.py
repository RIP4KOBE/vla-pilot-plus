"""Invented CPU records only; no historical tensor/provider/metric reads."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest
import torch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('test_n4_reader', HERE/'check_q0_transfer.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
DEFINITION = json.loads((HERE/'dependencies-v1.json').read_bytes())


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '')
    return m.dependencies(DEFINITION)


def fixture_rows(modules, *, actual_m=8, last_actions=None, last_costs=None, select_last=None, dtype=torch.bfloat16):
    rows=[]
    def emit(event, **values):
        row=dict(event=event, sequence=len(rows)+1, decision_id='synthetic-d0', global_step=0,
                 episode=0, reset_sequence=0, values=values)
        rows.append(row);return row
    emit('decision_context', stage=1, use_guidance=True, providers=[{'ordinal':0}])
    prior = None; first = None
    for j in range(11):
        iteration=j-1
        if prior is not None:
            actions,quality,cost=prior
            emit('archive_parent_allocation',iter_idx=iteration,parent_rewards=quality.float(),parent_costs=cost.float(),
                 parent_fingerprints=[m.fingerprint(a) for a in actions],parent_lanes=['quality']*16)
            emit('parent_allocation',iter_idx=iteration,source_population=actions.clone(),source_quality=quality.float(),
                 source_costs=cost.float(),elite_count=0,parent_indices=torch.arange(16,dtype=torch.int64))
        population=torch.zeros((16,64,128),dtype=dtype)
        population[:,:,39]=torch.arange(j*16,j*16+16,dtype=torch.float32).to(dtype)[:,None]/256
        population[:,:,10]=-1
        costs=torch.arange(j*100,j*100+16,dtype=torch.float32).to(dtype)
        if j==10:
            if last_actions is not None:population=last_actions.clone()
            if last_costs is not None:costs=last_costs.clone()
        quality=-costs
        scope={'role':'canonical_initial' if iteration==-1 else 'canonical_offspring','iter_idx':iteration,'site':'initial_population' if iteration==-1 else 'rollout'}
        score=emit('scoring_inputs',samples=population.clone(),scoring_scope=scope)
        emit('scoring_aggregate',scoring_batch_id=score['sequence'],scoring_scope=scope,aggregate_before_reward_mode=quality.clone())
        emit('effective_quality',scoring_batch_id=score['sequence'],scoring_scope=scope,reward_mode='normal',quality=quality.clone(),costs=costs.clone())
        emit('canonical_candidate_batch',iter_idx=iteration,candidates=population.clone(),effective_quality=quality.clone(),
             canonical_fingerprints=[m.fingerprint(a) for a in population],occurrence_ids=[f'j{j}:r{i}' for i in range(16)])
        if first is None:first=(population.clone(),quality.clone(),costs.clone())
        prior=(population,quality,costs)
    if select_last is None:selected=first[0][:1]; selected_quality=first[1][0].item();selected_cost=first[2][0].item()
    else:selected=prior[0][select_last:select_last+1];selected_quality=prior[1][select_last].item();selected_cost=prior[2][select_last].item()
    emit('final_selection',population=selected.clone(),selected_latent=selected.clone(),selected_index=0,
         selected_quality=selected_quality,selected_cost=selected_cost,selected_canonical_fingerprint=m.fingerprint(selected[0]),
         selected_fingerprint=m.fingerprint(selected[0]),selection_rule='archive_global_best')
    raw=selected.float();decoded=modules['decoder'].decode_rdt_libero_action_chunk(raw,8)
    emit('policy_action_decode',selected_latent=raw,action_chunk=decoded.clone(),selected_canonical_fingerprint=m.fingerprint(selected[0]))
    emit('decision_committed',action_chunk=decoded.clone(),execution_horizon=8)
    for i in range(actual_m):
        dispatch=emit('action_dispatch',execution_index=i+1);dispatch['global_step']=i
        emit('executed_action',action_numpy=decoded[0,i].clone())
        emit('pre_reset_outcome',terminated=i==actual_m-1 and actual_m<8)
        emit('step_returned',truncated=False)
    return rows


def last_template(dtype=torch.bfloat16):
    x=torch.zeros((16,64,128),dtype=dtype);x[:,:,10]=-1
    x[:,:,39]=torch.arange(160,176).to(dtype)[:,None]/256
    return x


def test_complete_native_same_call_and_hypothetical_decode(modules):
    v=m.check_guided(fixture_rows(modules),modules)
    assert len(v['canonical_batches'])==11 and v['canonical_evaluations']==176 and len(v['parent_rounds'])==10
    assert v['nonmember'] and v['different_actual_m'] and v['nonmember_and_actual_m_difference']
    assert v['alternative_first_index']==0 and v['minimum_cost_tie_indices']==[0,1,2]
    # BF16 storage rounds 1000,1001,1002 to the same native minimum: no FP32 reranking.
    assert v['canonical_batches'][-1]['stored_cost']['dtype']=='torch.bfloat16'
    assert v['actual_selected_cost']==0.0 and v['actual_prefix_length']==8


@pytest.mark.parametrize('kind',['inactive_dimension','after_horizon','signed_zero','gripper_zero','short_suffix','duplicate_tie','member_tie'])
def test_decode_effect_boundaries_and_all_ties(modules,kind):
    x=last_template();costs=torch.arange(1000,1016,dtype=torch.float32).to(torch.bfloat16)
    actual_m=3 if kind=='short_suffix' else 8; select_last=None
    candidate=torch.zeros((64,128),dtype=torch.bfloat16);candidate[:,10]=-1
    if kind=='inactive_dimension':candidate[:,2]=1
    elif kind=='after_horizon':candidate[8:,39]=1
    elif kind=='signed_zero':candidate[:,39]=-0.0
    elif kind=='gripper_zero':candidate[:,10]=0
    elif kind=='short_suffix':candidate[3:,39]=1
    elif kind=='duplicate_tie':candidate[:,39]=1
    elif kind=='member_tie':candidate[:,39]=1
    x[0]=candidate
    if kind=='duplicate_tie':x[1]=candidate;costs[1]=costs[0]
    if kind=='member_tie':
        x[1,:,39]=2;costs[0]=costs[1]=0;select_last=1
    rows=fixture_rows(modules,last_actions=x,last_costs=costs,actual_m=actual_m,select_last=select_last)
    v=m.check_guided(rows,modules)
    assert v['alternative_first_index']==0 and v['alternative_native_identity_differs']
    if kind in ('inactive_dimension','after_horizon','signed_zero'):
        assert not v['different_first8'] and not v['different_actual_m'] and not v['nonmember_and_actual_m_difference']
    elif kind=='short_suffix':assert v['different_first8'] and not v['different_actual_m'] and v['difference_only_after_m']
    elif kind=='member_tie':
        assert v['last_canonical_membership_indices']==[1] and v['different_actual_m'] and not v['nonmember_and_actual_m_difference']
    else:assert v['different_actual_m']
    if kind=='gripper_zero':assert all(c[6]==1 for c in v['alternative_hypothetical_commands_FP32']['values'])
    if kind=='duplicate_tie':assert v['minimum_cost_tie_native_ids'][0]==v['minimum_cost_tie_native_ids'][1]


def test_duplicate_actual_native_matches_are_all_retained(modules):
    x=last_template();x[0,:,39]=x[1,:,39]=0
    costs=torch.arange(1000,1016,dtype=torch.float32).to(torch.bfloat16);costs[0]=costs[1]=0
    v=m.check_guided(fixture_rows(modules,last_actions=x,last_costs=costs),modules)
    assert v['last_canonical_membership_indices']==[0,1]
    assert v['minimum_cost_tie_indices']==[0,1] and not v['alternative_native_identity_differs']
    assert len(v['actual_archive_slots'][0]['matching_occurrences'])==3


@pytest.mark.parametrize('defect',[ 'wrong_cost','wrong_dtype','wrong_score_id','auxiliary_substitution','duplicate_round','future_parent','parent_cost','actual_decode','dispatch','selected_cast','selected_cost','native_duplicate_quality'])
def test_required_association_unknown_prevents_activity_gate(modules,defect):
    rows=fixture_rows(modules)
    effects=[r for r in rows if r['event']=='effective_quality'];sources=[r for r in rows if r['event']=='scoring_inputs'];canonical=[r for r in rows if r['event']=='canonical_candidate_batch']
    if defect=='wrong_cost':effects[-1]['values']['costs'][0]+=16
    elif defect=='wrong_dtype':effects[-1]['values']['costs']=effects[-1]['values']['costs'].float()
    elif defect=='wrong_score_id':effects[-1]['values']['scoring_batch_id']=sources[-2]['sequence']
    elif defect=='auxiliary_substitution':sources[-1]['values']['scoring_scope']=dict(sources[-1]['values']['scoring_scope'],role='auxiliary_pretest')
    elif defect=='duplicate_round':rows.append(copy.deepcopy(canonical[-1]))
    elif defect=='future_parent':
        p=next(r for r in rows if r['event']=='parent_allocation');p['values']['source_population']=canonical[-1]['values']['candidates'].clone()
    elif defect=='parent_cost':next(r for r in rows if r['event']=='archive_parent_allocation')['values']['parent_costs'][0]+=1
    elif defect=='actual_decode':next(r for r in rows if r['event']=='policy_action_decode')['values']['action_chunk'][0,0,0]+=1
    elif defect=='dispatch':next(r for r in rows if r['event']=='executed_action')['values']['action_numpy'][0]+=1
    elif defect=='selected_cast':next(r for r in rows if r['event']=='policy_action_decode')['values']['selected_latent']=torch.zeros((1,64,128),dtype=torch.bfloat16)
    elif defect=='selected_cost':next(r for r in rows if r['event']=='final_selection')['values']['selected_cost']=1
    else:
        canonical[-1]['values']['candidates'][0]=canonical[0]['values']['candidates'][0]
        canonical[-1]['values']['canonical_fingerprints'][0]=m.fingerprint(canonical[-1]['values']['candidates'][0])
        sources[-1]['values']['samples'][0]=canonical[-1]['values']['candidates'][0]
        f=next(r for r in rows if r['event']=='final_selection');assert m.fingerprint(f['values']['selected_latent'][0])==canonical[-1]['values']['canonical_fingerprints'][0]
    value=m.inspect_decision(rows,modules)
    assert value['status']=='Unknown_required_association'
    result=m.summarize([{'decisions':[value]}],{'cells':1,'decisions':1,'guided':1,'actions':8})
    assert not result['gate_passed'] and result['unknown_required_associations']==1


def test_auxiliary_is_excluded_not_used_for_last_argmin(modules):
    rows=fixture_rows(modules);seq=max(r['sequence'] for r in rows)+1
    rows.append(dict(rows[0],event='scoring_inputs',sequence=seq,values={'samples':torch.zeros((16,64,128)), 'scoring_scope':{'role':'auxiliary_pretest','iter_idx':9,'site':'not_canonical'}}))
    v=m.check_guided(rows,modules);assert v['auxiliary_scoring_batches_excluded']==1 and v['alternative_first_index']==0


def test_off_disposition_and_short_terminal_count_are_preserved(modules):
    rows=fixture_rows(modules,actual_m=3);rows[0]['values']['use_guidance']=False
    value=m.inspect_decision(rows,modules)
    assert value['status']=='not_applicable_unguided' and value['comparison'] is None and value['actual_prefix_length']==3
    assert value['context_sequence']==1 and value['provider_identities']==[{'ordinal':0}]
    report=m.summarize([{'decisions':[value]}],{'cells':1,'decisions':1,'guided':0,'actions':3})
    assert report['actual_actions']==3 and not report['gate_passed']


def test_signed_zero_numeric_comparison_and_dtype_are_explicit():
    a=torch.tensor([0.],dtype=torch.float32);b=torch.tensor([-0.],dtype=torch.float32)
    assert m.numeric_same(a,b) and not m.numeric_same(a,b.double())


def test_incomplete_inventory_rejected(modules):
    known=m.inspect_decision(fixture_rows(modules),modules)
    with pytest.raises(ValueError,match='complete_known_inventory'):
        m.summarize([{'decisions':[known]}],{'cells':10,'decisions':825,'guided':155,'actions':6594})


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);data=json.dumps(value).encode();path.write_bytes(data)
    return {'path':str(path),'sha256':m.sha(data)}


def metadata_fixture(root,modules,defect=None):
    """Invented complete30 metadata, exact10 Q0 subset and task9-Q0 recovery."""
    import shutil
    old=m.load_module('synthetic_metadata_fixture',DEFINITION['test_sources']['v1_synthetic_metadata_fixture'])
    previous_manifest,previous_auth=old.identity_fixture(root)
    matrix=json.loads(Path(previous_manifest['matrix_report']['path']).read_bytes());authority=matrix['input_manifest']
    base=json.loads(Path(authority['base_plan']['path']).read_bytes());base['n3_cohort']['checkpoint_release']=None
    admission=json.loads(Path(DEFINITION['admission_definition']['path']).read_bytes())
    release=copy.deepcopy(admission['checkpoint_admission']['release_metadata'])
    release.update(source_files_sha256=m.sha(json.dumps(base['code_files'],sort_keys=True,separators=(',',':')).encode()),
                   protocol_sha256=base['n3_cohort']['protocol']['sha256'],attempt_ids=[c['valid_attempt_id'] for c in matrix['cells'][:3]])
    rr=put(root/'release.json',release)
    post=copy.deepcopy(base);post['n3_cohort']['checkpoint_release']=rr
    recovery=copy.deepcopy(post);original=base['episodes'][28]
    retry=dict(original,episode_key='t9-Q0-retry',retry_of='t9-Q0',budget_bucket='recovery');recovery['episodes'].append(retry)
    br=put(root/'base.json',base);pr=put(root/'post.json',post);recr=put(root/'recovery.json',recovery)
    authority.update(base_plan=br,plan_revisions=[pr,recr])
    extras={e['attempt_id']:e for e in previous_manifest['cells']};snaps={s['attempt_id']:s for s in previous_auth['completed_audit_snapshots']}
    for cell in matrix['cells']:
        saved=cell['attempts'][0];terminal=saved['terminal'];terminal['plan_sha256']=br['sha256']
        if cell['identity']['task_id']==9 and cell['identity']['profile']=='Q0':
            oldid=terminal['attempt_id'];newid='t9-Q0-retry';oldout=Path(terminal['output_dir']);newout=root/'attempts'/newid
            shutil.copytree(oldout,newout)
            invalid=copy.deepcopy(saved);invalid.update(status='terminal_invalid');invalid['terminal']['outcome_valid']=False
            invalid['references']={'terminal':put(oldout/'attempt-result.json',invalid['terminal'])}
            terminal.update(attempt_id=newid,episode_key=newid,output_dir=str(newout),retry_of=oldid,budget_bucket='recovery',plan_sha256=recr['sha256'])
            for key,ref in saved['references'].items():ref['path']=str(newout/Path(ref['path']).relative_to(oldout))
            ap=Path(saved['references']['audit']['path']);av=json.loads(ap.read_bytes());av.update(episode_dir=str(newout/'eds_eval/decision_evidence/episode_000'),episode_compute_file=str(newout/'eds_eval/episode_compute.jsonl'))
            saved['references']['audit']=put(ap,av)
            extra=extras.pop(oldid);extra['attempt_id']=newid
            for key in ('metadata','status','index'):extra[key]['path']=str(newout/Path(extra[key]['path']).relative_to(oldout))
            extras[newid]=extra;snaps.pop(oldid)
            snaps[newid]=dict(attempt_id=newid,audit=saved['references']['audit'],status=extra['status'],index=extra['index'],auditor_sha256=DEFINITION['reviewed_source_sha256']['scripts/audit_decision_evidence.py'],binding=modules['stream'].SNAPSHOT)
            cell.update(valid_attempt_id=newid,attempts=[invalid,saved])
        saved['references']['terminal']=put(Path(saved['references']['terminal']['path']),terminal)
    ar=put(root/'report-input.json',authority);matrix['input_manifest_sha256']=ar['sha256'];mr=put(root/'report.json',matrix)
    admission['checkpoint_admission']=dict(base_plan=br,plan_revisions=[pr,recr],checkpoint_release=rr,release_metadata=release,base_checkpoint_value=None)
    admission_ref=put(root/'admission-definition.json',admission)
    qc=[c for c in matrix['cells'] if c['identity']['profile']=='Q0']
    ex=[{k:extras[c['valid_attempt_id']][k] for k in ('attempt_id','metadata','status','index')} for c in qc]
    ss=[snaps[c['valid_attempt_id']] for c in qc]
    hashes={str(p):m.sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
    prov=put(root/'provenance.json',{'complete':True,'source_commit':m.SOURCE,'cuda_initialized':False,'new_quality_computation':False,'fresh_audit_calls':0,'input_hashes':hashes})
    definition=copy.deepcopy(DEFINITION);definition.update(matrix_report_sha256=mr['sha256'],matrix_input_sha256=ar['sha256'],completed_diagnostic_provenance_sha256=prov['sha256'],admission_definition=admission_ref)
    manifest={'schema':'n4-q0-transfer-input-v1','matrix_report':mr,'matrix_report_input':ar,'completed_diagnostic_provenance':prov,'cells':ex}
    manifest_ref=put(root/'manifest.json',manifest)
    auth={'manifest':manifest_ref,'reviewed_manifest':manifest_ref,'completed_Q0_scope_reviewed':True,'completed_audit_snapshots':ss,'reviewed_metadata_sources':previous_auth['reviewed_metadata_sources']}
    if defect=='universe':manifest['cells'][-1]=manifest['cells'][0]
    elif defect=='wrong_profile':manifest['cells'][-1]=previous_manifest['cells'][0]
    elif defect=='snapshot':auth['completed_audit_snapshots'][-1]['binding']='unverified'
    elif defect=='source':definition['reviewed_source_sha256']['main.py']='0'*64
    elif defect=='decoder':definition['modules']['decoder']['sha256']='0'*64
    elif defect=='metadata':auth['reviewed_metadata_sources']['scripts/qd_ed_n3_report.py']='0'*64
    elif defect=='status_bytes':Path(ex[-1]['status']['path']).write_text('{}')
    elif defect=='native_bytes':(Path(ex[-1]['status']['path']).parent/'bundle_000001.pt').write_bytes(b'changed')
    elif defect in ('recovery','last_audit'):
        if defect=='recovery':
            matrix['cells'][28]['attempts'][0]['terminal']['outcome_valid']=True
            mr=put(root/'report.json',matrix);definition['matrix_report_sha256']=mr['sha256'];manifest['matrix_report']=mr
        else:
            p=Path(qc[-1]['attempts'][-1]['references']['audit']['path']);p.write_text('{}')
    return manifest,auth,definition


def test_all10_metadata_admission_includes_only_accepted_task9_recovery(tmp_path,modules,monkeypatch):
    manifest,auth,definition=metadata_fixture(tmp_path,modules);inputs=modules['stream'].Inputs(tmp_path)
    called=[];monkeypatch.setattr(torch,'load',lambda *a,**k:called.append(True))
    admitted=m.admit(manifest,auth,definition,modules,inputs)
    assert len(admitted)==10 and admitted[-1]['terminal']['retry_of']=='t9-Q0'
    paths=list(inputs.hashes)
    assert len([p for p in paths if p.endswith('.pt')])==10 and not called
    assert all('Q0' in p for p in paths if '/attempts/' in p)
    assert not any('/attempts/t9-Q0/' in p for p in paths)
    assert not any(p.endswith('eds_metrics.jsonl') for p in paths)


@pytest.mark.parametrize('defect',['universe','wrong_profile','snapshot','source','decoder','metadata','status_bytes','native_bytes','recovery','last_audit'])
def test_bad_Q0_admission_never_decodes(tmp_path,modules,monkeypatch,defect):
    manifest,auth,definition=metadata_fixture(tmp_path,modules,defect);inputs=modules['stream'].Inputs(tmp_path)
    called=[];monkeypatch.setattr(torch,'load',lambda *a,**k:called.append(True))
    with pytest.raises(ValueError):m.admit(manifest,auth,definition,modules,inputs)
    assert called==[]
