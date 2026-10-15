import copy
import json
from pathlib import Path
import pytest
from scalar_summary_v1 import BoundedReader,build,summarize,MetadataError
from synthetic_summary_v1 import Fixture,metric

def review(f):return build(f.data,BoundedReader(f.files))
def test_hand_computed_mixed_arms_phases_and_partial_pairing(tmp_path):
    f=Fixture(tmp_path);r=review(f)
    assert r['cohort_disposition']=='INVALID_OR_INTERRUPTED' and r['describes_partial_prefix_only']
    assert r['original_accepted_prefix_cells']==7 and not r['next_gpu_execution_authorized']
    n25=r['arms']['N25'];n26=r['arms']['N26']
    assert n25['accepted_cells']==2 and n26['accepted_cells']==1
    a=n25['phases']['initial'];b=n26['phases']['initial']
    assert a['rbf_calls']==b['rbf_calls']==4 and a['input_components']==1536
    assert a['clipped_components_ratio']==.25 and b['clipped_components_ratio']==.5
    assert a['boundary_components']==192 and b['boundary_components']==0
    assert a['norms']['gradient_before_normalization']=={'count':4,'min':1.,'median':2.5,'mean':2.5,'max':4.}
    assert b['norms']['gradient_before_normalization']=={'count':4,'min':0.,'median':3.,'mean':3.,'max':6.}
    assert b['zero_gradient_ratio']==.25
    assert n26['phases']['rollout']['zero_gradient_calls']==15 and n26['phases']['rollout']['input_components']==5760
    assert r['pair_coverage']=={'accepted_matched_tasks':[0],'unmatched_tasks':{'N25':[1],'N26':[]},'matched_tasks_with_both_phase_observed':{'initial':1,'rollout':1}}
    pair=r['paired_task_phases'][0]
    assert pair['N26_minus_N25']['clipped_components_ratio']==.25
    assert pair['N26_minus_N25']['norm_mean_differences']['gradient_before_normalization']==.5
    assert len(r['decisions'])==2 and r['decisions'][1]['phases']['rollout']['zero_gradient_ratio']==1.
    assert r['files_read']==7  # Five control JSON + two present metrics; one attested absence.

def test_zero_guided_absent_phases_null(tmp_path):
    r=review(Fixture(tmp_path,n=4,all_zero_guided=True))
    for arm in r['arms'].values():
        for p in arm['phases'].values():
            assert p['rbf_calls']==0 and p['zero_gradient_ratio'] is None
            assert p['norms']['update_operand']=={'count':0,'min':None,'median':None,'mean':None,'max':None}
    assert all(x['N26_minus_N25']['zero_gradient_ratio'] is None for x in r['paired_task_phases'])

def test_all_zero_gradient_is_descriptive_not_rejected():
    r=summarize([{'arm':'N26','task_id':0,'attempt_id':'synthetic','metrics_present':True,'metrics':[metric('N26',zero=True)]}])
    assert r['arms']['N26']['phases']['initial']['zero_gradient_ratio']==1.
    assert r['arms']['N26']['phases']['initial']['norms']['update_operand']['mean']==0.

def test_unequal_guided_counts_keep_decisions_distinct():
    r=summarize([{'arm':'N25','task_id':0,'attempt_id':'left','metrics_present':True,'metrics':[metric('N25'),metric('N25',8)]},
                 {'arm':'N26','task_id':0,'attempt_id':'right','metrics_present':True,'metrics':[metric('N26')]}])
    pair=r['paired_task_phases'][0]
    assert pair['call_denominators']=={'N25':8,'N26':4}
    assert pair['component_denominators']=={'N25':3072,'N26':1536} and len(r['decisions'])==3

@pytest.mark.parametrize('change',['missing','extra','duplicate','reorder'])
def test_no_cell_subselection(tmp_path,change):
    f=Fixture(tmp_path)
    if change=='missing':f.data['metrics'].pop()
    if change=='extra':f.data['metrics'].append(copy.deepcopy(f.data['metrics'][0]))
    if change=='duplicate':f.data['metrics'][1]=copy.deepcopy(f.data['metrics'][0])
    if change=='reorder':f.data['metrics'].reverse()
    with pytest.raises(MetadataError):review(f)

def replace(f,role,mutate):
    q=copy.deepcopy(f.values[f.refs[role]['path']]);mutate(q);f.put(role,q)

@pytest.mark.parametrize('change',['source','receipt','review_disposition','inventory_hash'])
def test_control_identity_mismatch(tmp_path,change):
    f=Fixture(tmp_path)
    if change=='source':replace(f,'source',lambda x:x.update(commit='5a65ef15968cc68c82314e8c0773b3365ad45fa0'))
    if change=='receipt':replace(f,'result',lambda x:x['accepted_cells'][2]['worker_receipt'].update(sha256='f'*64))
    if change=='review_disposition':replace(f,'terminal_review',lambda x:x.update(cohort_disposition='REJECT'))
    if change=='inventory_hash':f.data['refs']['terminal_input']={**f.refs['terminal_input'],'sha256':'f'*64}
    with pytest.raises(MetadataError):review(f)

@pytest.mark.parametrize('kind',['duplicate_call','missing_call','nonfinite','components','wrong_source','missing_stride'])
def test_scalar_schema_negative(kind):
    m=metric('N26');row=m['initial_direction_rbf_evidence_by_step'][0]
    if kind=='duplicate_call':m['initial_direction_rbf_evidence_by_step'][1]=copy.deepcopy(row)
    if kind=='missing_call':m['initial_direction_rbf_evidence_by_step'].pop()
    if kind=='nonfinite':row['update_operand']['norm']=float('inf')
    if kind=='components':row['clipped_components']=385
    if kind=='wrong_source':row['input_source']='noisy_sample'
    if kind=='missing_stride':row.pop('input_stride')
    with pytest.raises(MetadataError):summarize([{'arm':'N26','task_id':0,'attempt_id':'x','metrics_present':True,'metrics':[m]}])

def test_input_cap_hash_and_raw_fallback(tmp_path):
    f=Fixture(tmp_path)
    old=copy.deepcopy(f.files)
    f.files[0]['bytes']=16*1024*1024+1
    with pytest.raises(MetadataError):BoundedReader(f.files)
    f.files[:]=copy.deepcopy(old);f.files.append(copy.deepcopy(f.files[-1]))
    with pytest.raises(MetadataError):BoundedReader(f.files)
    f.files[:]=copy.deepcopy(old);f.files[0]['path']=str(tmp_path/'events.jsonl')
    with pytest.raises(MetadataError):BoundedReader(f.files)
    f.files[:]=copy.deepcopy(old)
    Path(f.refs['source']['path']).write_text('{}')
    with pytest.raises(MetadataError,match='input drift'):review(f)

def test_absent_metric_created_later_rejected(tmp_path):
    f=Fixture(tmp_path);absent=next(x for x in f.files if not x['present']);Path(absent['path']).write_text('')
    with pytest.raises(MetadataError,match='absence changed'):review(f)

def test_disabled_manifest_rejected(tmp_path):
    f=Fixture(tmp_path);f.data['executable']=False
    with pytest.raises(MetadataError,match='disabled'):review(f)

def rebind_terminal_inventory(f,value):
    f.put('terminal_input',value)
    r=copy.deepcopy(f.values[f.refs['terminal_review']['path']]);r['input_manifest']=f.refs['terminal_input'];f.put('terminal_review',r)

def test_receipt_scope_failure_beyond_hash_gate(tmp_path):
    f=Fixture(tmp_path)
    q=copy.deepcopy(f.values[f.refs['terminal_input']['path']]);q['attempts'][2]['refs']['receipt']['sha256']='e'*64
    rebind_terminal_inventory(f,q)
    with pytest.raises(MetadataError,match='receipt scope'):review(f)

def test_attested_missing_positive_metrics_rejected(tmp_path):
    f=Fixture(tmp_path);entry=next(x for x in f.files if x['role']=='metrics' and x['present'])
    Path(entry['path']).unlink();entry.update(present=False,sha256=None,bytes=0)
    target=next(x for x in f.data['metrics'] if x['ref']['path']==entry['path']);target['ref']['sha256']=None
    q=copy.deepcopy(f.values[f.refs['terminal_input']['path']])
    declaration=next(x for x in q['files'] if x['path']==entry['path']);declaration.update(present=False,sha256=None,bytes=0)
    attempt=next(x for x in q['attempts'] if x['attempt_id']==target['attempt_id']);attempt['refs']['metrics']['sha256']=None
    rebind_terminal_inventory(f,q)
    with pytest.raises(MetadataError,match='missing positive-guided'):review(f)

def test_extra_unselected_metric_file_rejected(tmp_path):
    f=Fixture(tmp_path);f.put('metrics',[metric('N25')],tmp_path/'extra.jsonl')
    with pytest.raises(MetadataError,match='extra metric'):review(f)

def test_nonfinite_json_and_duplicate_keys_rejected(tmp_path):
    import hashlib
    for text in ('{"x":1,"x":2}', '{"x":NaN}'):
        f=Fixture(tmp_path/str(len(text)))
        r=next(x for x in f.files if x['role']=='terminal_review');blob=text.encode();Path(r['path']).write_bytes(blob)
        r.update(bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest());f.refs['terminal_review']['sha256']=r['sha256']
        with pytest.raises(MetadataError):review(f)

def test_total_files_and_bytes_bound_before_open(tmp_path):
    f=Fixture(tmp_path)
    records=copy.deepcopy(f.files)
    for i in range(9):
        records.append({'role':'metrics','path':str(tmp_path/f'large{i}.jsonl'),'present':True,'sha256':'a'*64,'bytes':16*1024*1024})
    with pytest.raises(MetadataError,match='finite role coverage'):BoundedReader(records)
    with pytest.raises(MetadataError,match='metadata count'):BoundedReader([{}]*33)

def test_empty_prefix_keeps_unknown_distribution(tmp_path):
    r=review(Fixture(tmp_path,n=0))
    assert r['original_accepted_prefix_cells']==0 and r['describes_partial_prefix_only']
    assert r['pair_coverage']['accepted_matched_tasks']==[]
    assert r['arms']['N26']['phases']['initial']['norms']['update_operand']['mean'] is None

def test_cli_disabled_and_complete_owned_summary(tmp_path,monkeypatch):
    import scalar_summary_v1 as s
    f=Fixture(tmp_path);input_path=tmp_path/'input.json';output=tmp_path/'summary.json'
    monkeypatch.setattr(s,'HERE',tmp_path)
    monkeypatch.setattr(s.sys,'argv',['scalar_summary_v1.py','--input',str(input_path),'--output',str(output)])
    f.data['executable']=False;input_path.write_text(json.dumps(f.data))
    with pytest.raises(MetadataError,match='disabled'):s.main()
    assert not output.exists()
    f.data['executable']=True;input_path.write_text(json.dumps(f.data));s.main()
    value=json.loads(output.read_text())
    assert value['cohort_disposition']=='INVALID_OR_INTERRUPTED' and len(value['tasks'])==3
    assert value['input_manifest']['path']==str(input_path) and not value['next_gpu_execution_authorized']
    with pytest.raises(MetadataError,match='owned immutable'):s.main()
    s.signal.alarm(0)
