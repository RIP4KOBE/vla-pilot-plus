"""N35 four-arm composition and prospective source/runtime closure. No adoption."""
import copy
import hashlib
import json
from pathlib import Path
from scripts import qd_ed_n23_worker as w, qd_ed_n34_bridge as n34
from scripts import qd_ed_n34_source as closure, qd_ed_n35_contract as c
from core.qd_closure_intent import MODE, SOURCE_FILES

ROOT=Path(__file__).resolve().parents[1]
RUNTIME_SOURCES=SOURCE_FILES
runner=n34.runner
compose_launch=n34.compose_launch
resolve_constructor=n34.resolve_constructor
runtime_sources=lambda root=ROOT: SOURCE_FILES


def source_paths(root=ROOT):
    root=Path(root)
    paths=set(runner.REQUIRED_CODE) | {'main.py'}
    for folder,pattern in (('core','*.py'),('scripts','*.py'),('utils','*.py'),('vlm_query','*.py'),('vlm_query','*.txt'),
                           ('configs','*.yaml'),('configs','*.yml'),('configs','*.json'),('tests','*n35*.py'),('patches','*.py')):
        paths.update(str(p.relative_to(root)) for p in (root/folder).rglob(pattern))
    paths.update(closure.dependency_paths(root))
    return paths


def scientific_paths(root=ROOT):
    return source_paths(root)


def profiles(root=ROOT):
    result=n34.profiles(root)
    active=copy.deepcopy(result['profiles']['N34'])
    active['historical_label']='N35'
    active['restored_profile']['closure_intent_mode']=MODE
    active['resolved_eds_config']['closure_intent_mode']=MODE
    active['static_override_values']['main.eds_config.closure_intent_mode']=MODE
    active['hydra_overrides']=[f'{k}={runner.hydra(v)}' for k,v in active['static_override_values'].items()]
    result['profiles']['N35']=active
    return result


def command(plan,runtime,row):
    w.require(row in plan['episodes'] and row in c.expected_rows(plan['worktree']),'exact fresh N35 matrix row')
    argv,output=runner.build_command(plan,profiles(plan['worktree']),runtime,row,row['episode_key'])
    if row['profile'] in ('N34','N35'):
        binding={'task_id':row['task_id'],'source_commit':plan['source']['commit'],'run_id':row['episode_key']}
        for name in (('n34','n35') if row['profile']=='N35' else ('n34',)):
            argv.append('main.eds_config.'+name+'_runtime_binding={'+','.join(f'{k}:{runner.hydra(v)}' for k,v in binding.items())+'}')
    return argv,output


def manifest(plan,runtime,row):
    task=runtime['tasks'][str(row['task_id'])];files={v['path']:v['sha256'] for v in runtime['files']}
    w.require(task['task_id']==row['task_id'] and task['init_index']==row['init_index']
        and files[task['init_path']]==row['init_file_sha256'] and files[task['bddl_path']]==row['bddl_sha256'],'runtime task hashes')
    argv,output=command(plan,runtime,row);config,resolved=compose_launch(argv,plan['worktree'])
    w.require(config['backend']['libero']['max_episode_steps']==720 and config['policy']['rdt']['control_frequency']==20
        and config['policy']['rdt']['action_chunk_horizon']==8,'frozen schedule')
    w.require(resolved['capture_dwell_proposal_mode']==resolved['archive_eligible_capture_mode']=='off'
        and resolved['n32_runtime_binding'] is None,'exclusive modes')
    w.require(resolved['closure_intent_mode']==(MODE if row['profile']=='N35' else 'off')
        and resolved['observed_jaw_approach_mode']==(n34.MODE if row['profile'] in ('N34','N35') else 'off'),'four-arm modes')
    expected=None
    if row['profile'] in ('N34','N35'):
        binding={'task_id':row['task_id'],'source_commit':plan['source']['commit'],'run_id':row['episode_key']}
        w.require(resolved['n34_runtime_binding']==binding and resolved['n35_runtime_binding']==(binding if row['profile']=='N35' else None),'runtime binding')
        index={x['path']:x['sha256'] for x in plan['source']['files']}
        names=SOURCE_FILES if row['profile']=='N35' else n34.runtime_sources(plan['worktree'])
        expected={'binding':binding,'config_sha256':hashlib.sha256(json.dumps(resolved,sort_keys=True,allow_nan=False).encode()).hexdigest(),
            'source_hashes':{name:index[name] for name in names}}
    else:w.require(resolved['n34_runtime_binding'] is None and resolved['n35_runtime_binding'] is None,'control binding')
    return {'schema':'n35-external-runtime-v1','row':row,'source':plan['source'],'scientific_source':plan['scientific_source'],
        'runtime':plan['runtime'],'runtime_closure':plan['runtime_closure'],'controller_semantics':plan['controller_semantics'],
        'argv':argv,'output_dir':str(output),'composed_config_sha256':w.canonical_sha(config),
        'resolved_config':resolved,'expected_runtime':expected}


def verify_sources(plan):
    w.require(plan['source']==plan['scientific_source'],'single adopted N35 source across four arms')
    closure.verify_source(plan['worktree'],plan['source'])
    w.require(source_paths(plan['worktree']) <= {x['path'] for x in plan['source']['files']},'N35 source closure incomplete')


def _verify_manifest_bound(reference,plan,runtime,row):
    actual=w.read_ref(reference)
    w.require(actual==json.loads(json.dumps(manifest(plan,runtime,row))),'external manifest differs')
    return actual


def verify_manifest(reference,plan,runtime,row):
    verify_sources(plan)
    w.require(w.read_ref(plan['runtime'])==runtime,'runtime changed')
    closure.verify_runtime(w.read_ref(plan['runtime_closure']),plan['runtime'])
    return _verify_manifest_bound(reference,plan,runtime,row)


attest_loaded=closure.attest_loaded
