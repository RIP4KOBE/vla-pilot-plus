"""Continue after expected output-path relocation tripped an auxiliary comparison.
Production validators and already generated immutable artifacts are unmodified.
"""
import os, sys, json, time, copy, importlib.util
from pathlib import Path
OUT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('owner_composition',OUT/'compose-owner-v1.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
h.guard();os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
before=h.read(h.ref(OUT/'preservation-before-v1.json'))
assert h.snapshot()==before
failure=h.read(h.ref(OUT/'composition-failure-v1.json'))
assert failure['error']=="AssertionError('scientific configuration drift')"
assert all(x['status']=='PASS' for x in failure['checks'].values())
h.CHECKS.update(failure['checks'])
sys.path.insert(0,str(h.ROOT))
from scripts import qd_ed_n36_bridge as b, qd_ed_n36_contract as c, qd_ed_n36_recovery as recovery
from scripts import qd_ed_n36_release as release
plan=h.read(h.ref(OUT/'draft/plan.draft.json'))
previous=h.read(h.ref(h.TURNS/'001219/runtime-input-repair/report-v1.json'))
oldplan=h.read(previous['candidate'])
runtime=h.read(plan['runtime'])
adoption=h.read(h.read(h.ref(OUT/'authority-v1.json'))['adoption'])
metadata={k:oldplan[k] for k in ('run_name','input_contract_label','attempt_identity')}
for kind,filename in [('runtime_inventory','runtime-inventory.json'),('seed_plan','frozen-seed-plan.json')]:
    path=h.ROOT/'data'/filename;assert h.sha(path)==oldplan[kind+'_sha256']
    metadata[kind+'_path']=str(path);metadata[kind+'_sha256']=oldplan[kind+'_sha256']
plan.update(metadata,runtime_ready=True,root_approval_granted=False,readiness_scope='Inherited turn1223 readiness; byte-verified owning rebind. No current live-device claim; not release authority.')
h.check('metadata_complete_draft_final',lambda:c.validate_draft(plan))
authority=h.read(adoption['adopted_authority'])
h.check('adopted_authority_exact_refs_final',lambda:recovery.validate_authority(plan,authority))
h.check('unchanged_caps',lambda:release.validate_caps(authority['caps']))
state=b.runner.read_state(h.ROOT/'research-state.yaml')
assert state['n36_budget_authority']==adoption['adopted_authority']
assert state['budget']['amendment']==adoption['adopted_amendment']==plan['accounting']
assert state['budget']['max_episode_attempts']==authority['caps']['attempts']
assert state['budget']['max_gpu_hours']==authority['caps']['gpu_hours']
assert state['budget']['reserved']==authority['caps']['buckets']
assert state['budget']['gpu_hour_reservations']==authority['caps']['protected_gpu_hours']
assert state['resource_isolation']['status']=='ACTIVE' and state['resource_isolation']['validation_status']=='PASS'
rows=[];config_changes=[]
def differences(a,b,path=''):
    if isinstance(a,dict) and isinstance(b,dict):
        result=[]
        for k in sorted(a.keys()|b.keys()):result.extend(differences(a.get(k),b.get(k),path+'/'+k))
        return result
    return [] if a==b else [{'field':path,'before':a,'after':b}]
for row in plan['episodes']:
    m=h.check('manifest_'+row['episode_key'],lambda row=row:b._verify_manifest_bound(plan['expected_manifests'][row['episode_key']],plan,runtime,row))
    old=h.read(oldplan['expected_manifests'][row['episode_key']])
    changes=differences(old['resolved_config'],m['resolved_config'])
    for change in changes:
        if change['field']=='/mechanism_pretest/output_dir':
            assert change['after']==change['before'].replace(oldplan['artifact_root'],plan['artifact_root'])
        elif change['field'] in ('/n34_runtime_binding/source_commit','/n36_runtime_binding/source_commit'):
            assert change['before']==oldplan['source']['commit'] and change['after']==h.SOURCE
        else:raise AssertionError('unexpected scientific configuration difference: '+repr(change))
    assert row==old['row']
    config_changes.append({'episode_key':row['episode_key'],'changes':changes})
    rows.append({'episode_key':row['episode_key'],'profile':row['profile'],'manifest':plan['expected_manifests'][row['episode_key']],'composed_config_sha256':m['composed_config_sha256'],'scientific_config_unchanged_except_exact_source_and_output_bindings':True})
assert plan['episodes']==oldplan['episodes'] and len(rows)==40
planref=h.write('draft/plan.metadata-complete.draft.json',plan)
h.write('all40-composition-v1.json',{'expected':40,'actual':len(rows),'all_pass':True,'rows':rows,'task_seed_arm_order_unchanged':True,'configuration_rebinds':config_changes})
h.write('adopted-accounting-bindings-v1.json',{'plan':planref,'authority':adoption['adopted_authority'],'accounting':plan['accounting'],'amendment':adoption['adopted_amendment'],'protocol':plan['protocol'],'protocol_review':plan['protocol_review'],'root_adoption':h.read(h.ref(OUT/'authority-v1.json'))['adoption'],'draft_authority_is_null_by_strict_contract':True,'owning_state_exact_authority_amendment_caps_equalities':'PASS','adopted_snapshot':adoption['retained_snapshot'],'retained_margin_gpu_hours':adoption['retained_margin_gpu_hours'],'conservative_charge_gpu_hours':adoption['conservative_charge_gpu_hours'],'accounting_recomputed':False})
events=[json.loads(line) for line in (h.ROOT/'data/attempt-ledger.jsonl').read_text().splitlines() if 'n36_dev_t00_c0_001147' in line]
h.check('original_aborted_charge_preserved',lambda:recovery.preserve_charge(events))
after=h.snapshot();assert before==after,'owner state/source status changed during composition'
h.write('preservation-after-v1.json',{'snapshot':after,'equals_before':True,'source_strict_unchanged':True,'STOP_present':os.path.lexists(h.STOP)})
h.write('checks-v1.json',h.CHECKS)
h.write('comparison-resolution-v1.json',{'retained_failure':h.ref(OUT/'composition-failure-v1.json'),'cause':'Auxiliary comparison did not account for mechanism_pretest.output_dir moving to the newly authorized artifact directory.','source_defect':False,'production_validation_failure':False,'source_or_validator_modified':False,'resolution':'Allow only exact old/new artifact-root substitution and adopted source commit bindings; reject every other difference. All40 compared and strict manifests passed.','continuation':h.ref(__file__)})
h.write('composition-result-v1.json',{'status':'PASS_CPU_OWNER_BOUND_ALL40_DISABLED','plan':planref,**{k:plan[k] for k in ('runtime','runtime_closure','controller_semantics','native_build')},'source':h.SOURCE,'release_enabled':False,'frozen':False,'inherited_readiness_preserved':True,'native_readiness':False,'scientific_success':False,'target_met':False,'root_approval_granted':False})
