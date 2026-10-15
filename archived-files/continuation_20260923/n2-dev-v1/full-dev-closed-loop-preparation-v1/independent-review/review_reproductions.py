"""Source-only synthetic reproduction; no episode input, dependency, model or GPU read."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

SOURCE=Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-decision-evidence-20260923/docs/03_evidence/qd_ed_final/continuation_20260923/full-dev-closed-loop-preparation/read_full_dev.py')
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()=='f949cf780699e812143c5d089f358d0f9c40dc1517465ac8ac7d6c2bf8306a95'
spec=importlib.util.spec_from_file_location('reviewed_full_dev_source',SOURCE)
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
decisions=[{'global_step':0,'last_executed_step':7,'executed_prefix_length':8,'decision_id':'d0','reset_sequence':0,'stage':1,'use_guidance':True},
           {'global_step':8,'last_executed_step':8,'executed_prefix_length':1,'decision_id':'d1','reset_sequence':0,'stage':1,'use_guidance':False}]
steps=[{'global_step':i,'reset_sequence':0,'terminated':False,'truncated':False,'command':{'value':[0.]*6+[-1.]}} for i in range(9)]
common={'episode_id':0,'task_id':0,'episode_seed':100,'query_status':'ok','gripper_value_used':-1.}
results=[]
for name,event in [
    ('null_global_step',{**common,'global_step':None,'stage_after':1,'guidance_after':False}),
    ('missing_optional_after_state',{**common,'global_step':8}),
    ('present_known_after_state',{**common,'global_step':8,'stage_after':1,'guidance_after':False}),
]:
    try:
        value=r.joined_stage([event],decisions,steps)
        results.append({'case':name,'raised':False,'association':value['associations'][0]})
    except Exception as error:
        results.append({'case':name,'raised':True,'error_type':type(error).__name__,'error':str(error)})
results.append({'case':'absent_stage','value':r.joined_stage(None,decisions,steps)})
results.append({'case':'present_empty_stage','value':r.joined_stage([],decisions,steps)})
assert results[0]['error_type']=='TypeError'
assert results[1]['association']['same_step_context_agrees'] is False
assert results[2]['association']['same_step_context_agrees'] is True
assert results[3]['value']['events'] is None and results[4]['value']['events']==[]
assert 'torch' not in sys.modules
out={'scope':'synthetic association dictionaries only; no actual episodes, bundles or source dependency imports',
     'reviewed_source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
     'reproduction_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
     'torch_imported':False,'results':results}
with Path(__file__).with_name('reproductions-v1.json').open('x') as f:
    json.dump(out,f,indent=2);f.write('\n')
print(json.dumps({'reproduced':['null_global_step_TypeError','missing_after_state_false_instead_of_unknown'],
                  'control_cases':['known_after_state','absent_stage','present_empty_stage'],'torch_imported':False}))
