"""Bounded post-cell N21/N22 native contrast; no unexecuted-action outcomes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import torch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('control_reader',HERE/'n21_control_parity_cpu_v1.py')
reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
reader.FIELDS['archive_parent_allocation']=('iter_idx','parent_fingerprints')
reader.FIELDS['decision_context']=('use_guidance',)
IDS=('rdt-qd-ed-final-20260921T093925Z__n22_dev_t01_n21_20260930__e120fd199382',
     'rdt-qd-ed-final-20260921T093925Z__n22_dev_t01_n22_20260930__08ebc428b0b3')


def mapping(events, kind, iterative=False):
    result={}
    for step,value in events[kind]:
        key=(step,value['iter_idx']) if iterative else step
        assert key not in result
        result[key]=value
    return result


def main():
    torch.set_num_threads(1)
    target=HERE/'task1-trace-contrast-result-v1.json';assert not target.exists()
    left,lref=reader.read(IDS[0]);right,rref=reader.read(IDS[1])
    identity_keys=('task_id','env_seed','policy_seed','init_index','split')
    assert all(lref['matched_identity'][k]==rref['matched_identity'][k] for k in identity_keys)
    ldec,rdec=(mapping(x,'policy_action_decode') for x in (left,right))
    assert set(ldec)==set(rdec)==set(range(0,720,8))
    action_changes=[s for s in sorted(ldec) if not reader.equal(ldec[s]['action_chunk'],rdec[s]['action_chunk'])]
    first=action_changes[0] if action_changes else None
    boundary=first if first is not None else 720
    lcan,rcan=(mapping(x,'canonical_candidate_batch',True) for x in (left,right))
    common=sorted(set(lcan)&set(rcan))
    prefix=[]
    for key in common:
        if key[0]>boundary:continue
        a,b=lcan[key],rcan[key]
        pool=reader.equal(a['candidates'],b['candidates'])
        prefix.append({'step':key[0],'iter_idx':key[1],'same_native_pool':pool,
                       'same_raw_provider_quality':reader.equal(a['raw_provider_quality'],b['raw_provider_quality']),
                       'effective_quality_differences':int((a['effective_quality']!=b['effective_quality']).sum()) if pool else None})
    lp,rp=(mapping(x,'archive_parent_allocation',True) for x in (left,right))
    parent_changes=[{'step':s,'iter_idx':i,'changed_slots':sum(a!=b for a,b in zip(lp[s,i]['parent_fingerprints'],rp[s,i]['parent_fingerprints']))}
                    for s,i in sorted(set(lp)&set(rp)) if s<=boundary
                    and lp[s,i]['parent_fingerprints']!=rp[s,i]['parent_fingerprints']]
    ls,rs=(mapping(x,'terminal_population_stage_binding') for x in (left,right))
    stage_changes=[]
    for step in sorted(set(ls)&set(rs)):
        fields=[k for k in reader.FIELDS['terminal_population_stage_binding'] if not reader.equal(ls[step].get(k),rs[step].get(k))]
        if fields:stage_changes.append({'step':step,'different_fields':fields,'before_or_at_first_changed_action_chunk':step<=boundary})
    lc,rc=(mapping(x,'decision_context') for x in (left,right))
    guidance_changes=[s for s in sorted(set(lc)&set(rc)) if lc[s]['use_guidance']!=rc[s]['use_guidance']]
    out={'schema':'n22-task1-paired-trace-contrast-v1','sources':[lref,rref],
         'reader_sha256':reader.sha(__file__),'dependency_reader_sha256':reader.sha(reader.__file__),
         'matched_identity':{k:lref['matched_identity'][k] for k in identity_keys},
         'first_changed_executed_chunk':first,'changed_executed_chunk_steps':action_changes,
         'shared_canonical_batches':len(common),'n21_canonical_batches':len(lcan),'n22_canonical_batches':len(rcan),
         'native_prefix_comparisons':prefix,'parent_changes_through_first_changed_chunk':parent_changes,
         'stage_binding_changes':stage_changes,'guidance_activity_changed_steps':guidance_changes,
         'interpretation':'Both task1 arms are native-valid failures. Prefix comparison is descriptive matched-run mechanism evidence; after the first changed executed action, pools/states differ and cannot be treated as fixed-state counterfactuals. Effective archive cost-spread changes can also affect unchanged Stage normalization. No new task-efficacy or generalization claim.'}
    with target.open('x') as f:f.write(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:out[k] for k in ('first_changed_executed_chunk','changed_executed_chunk_steps','shared_canonical_batches','n21_canonical_batches','n22_canonical_batches','parent_changes_through_first_changed_chunk','stage_binding_changes','guidance_activity_changed_steps')}))


if __name__=='__main__':main()
