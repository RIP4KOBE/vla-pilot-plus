"""N36 four-arm composition and prospective source/runtime closure. No adoption."""
import copy
import hashlib
import json
from pathlib import Path
from scripts import qd_ed_n23_worker as w, qd_ed_n34_bridge as n34
from scripts import qd_ed_n34_source as closure, qd_ed_n36_contract as c
from core.qd_nonprogress_tangent import MODE, SOURCE_FILES

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
                           ('configs','*.yaml'),('configs','*.yml'),('configs','*.json'),('tests','*n36*.py'),('patches','*.py')):
        paths.update(str(p.relative_to(root)) for p in (root/folder).rglob(pattern))
    paths.update(closure.dependency_paths(root))
    return paths


def scientific_paths(root=ROOT):
    return source_paths(root)


def profiles(root=ROOT):
    result=n34.profiles(root)
    for control in result['profiles'].values():
        for config in (control['restored_profile'],control['resolved_eds_config']):
            config.update(closure_intent_mode='off',n35_runtime_binding=None,nonprogress_tangent_mode='off',n36_runtime_binding=None)
        control['static_override_values'].update({'main.eds_config.closure_intent_mode':'off','main.eds_config.n35_runtime_binding':None,'main.eds_config.nonprogress_tangent_mode':'off','main.eds_config.n36_runtime_binding':None})
        control['hydra_overrides']=[f'{k}={runner.hydra(v)}' for k,v in control['static_override_values'].items()]
    active=copy.deepcopy(result['profiles']['N34'])
    active['historical_label']='N36'
    active['restored_profile']['nonprogress_tangent_mode']=MODE
    active['resolved_eds_config']['nonprogress_tangent_mode']=MODE
    active['static_override_values']['main.eds_config.nonprogress_tangent_mode']=MODE
    active['hydra_overrides']=[f'{k}={runner.hydra(v)}' for k,v in active['static_override_values'].items()]
    result['profiles']['N36']=active
    return result


def command(plan,runtime,row):
    from scripts import qd_ed_n36r4_admission as successor
    audit_only = plan.get('schema') == 'n36-engineering-audit-view-v1'
    if audit_only:
        from scripts.qd_ed_n36_engineering_api import for_plan
        validate_audit_view = for_plan(plan).validate_audit_view
        validate_audit_view(plan, require_manifests=False)
    if not audit_only and (c.cohort(plan) == c.DRAFT_N36R4_COHORT
            or (plan.get('protocol') or {}).get('sha256') == successor.PROTOCOL_SHA
            or (plan.get('accounting') or {}).get('sha256') == successor.ACCOUNTING_SHA):
        successor.validate_protocol(plan)
    w.require(row in plan['episodes'] and row in c.plan_rows(plan),'exact fresh N36 matrix row')
    argv,output=runner.build_command(plan,profiles(plan['worktree']),runtime,row,row['episode_key'])
    if c.cohort(plan) == c.DRAFT_N36R4_COHORT:
        # Preserve the exact prospective owner spelling and keep reports out of
        # source/historical evidence directories. validate_protocol pins both
        # the lexical artifact root and its physical session destination.
        output = Path(plan['artifact_root']) / 'attempts' / row['episode_key']
        routes = {'hydra.run.dir': output,
                  'main.eds_eval.output_dir': output / 'eds_eval',
                  'main.eds_eval.report_dir': (Path(plan['artifact_root']) / 'reports' if audit_only else
                                               Path(plan['artifact_root']).parent / 'prospective-reports-001467'),
                  'main.eds_mechanism_pretest.output_dir': output / 'mechanism'}
        for key, destination in routes.items():
            w.require(sum(arg.startswith(key + '=') for arg in argv) == 1,
                      'N36R4 exact output override coverage')
            argv = [key + '=' + str(destination) if arg.startswith(key + '=') else arg
                    for arg in argv]
    if row['profile'] in ('N34','N36'):
        binding={'task_id':row['task_id'],'source_commit':plan['source']['commit'],'run_id':row['episode_key']}
        for name in (('n34','n36') if row['profile']=='N36' else ('n34',)):
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
    w.require(resolved['closure_intent_mode']=='off' and resolved['n35_runtime_binding'] is None,'N35 disabled in all arms')
    w.require(resolved['nonprogress_tangent_mode']==(MODE if row['profile']=='N36' else 'off')
        and resolved['observed_jaw_approach_mode']==(n34.MODE if row['profile'] in ('N34','N36') else 'off'),'four-arm modes')
    expected=None
    if row['profile'] in ('N34','N36'):
        binding={'task_id':row['task_id'],'source_commit':plan['source']['commit'],'run_id':row['episode_key']}
        w.require(resolved['n34_runtime_binding']==binding and resolved['n36_runtime_binding']==(binding if row['profile']=='N36' else None),'runtime binding')
        index={x['path']:x['sha256'] for x in plan['source']['files']}
        names=SOURCE_FILES if row['profile']=='N36' else n34.runtime_sources(plan['worktree'])
        expected={'binding':binding,'config_sha256':hashlib.sha256(json.dumps(resolved,sort_keys=True,allow_nan=False).encode()).hexdigest(),
            'source_hashes':{name:index[name] for name in names}}
    else:w.require(resolved['n34_runtime_binding'] is None and resolved['n36_runtime_binding'] is None,'control binding')
    audit_tags = ({'schema': 'n36-engineering-audit-runtime-v1',
                   'original_plan': plan['original_plan'], 'scope': plan['scope'],
                   'deployment': plan['deployment'], 'dispatch_authority': False}
                  if plan.get('schema') == 'n36-engineering-audit-view-v1' else {})
    return {**c.operational_binding(plan), 'schema':'n36-external-runtime-v1', **audit_tags,'row':row,'source':plan['source'],'scientific_source':plan['scientific_source'],
        'native_build':plan['native_build'],'runtime':plan['runtime'],'runtime_closure':plan['runtime_closure'],'controller_semantics':plan['controller_semantics'],
        'argv':argv,'output_dir':str(output),'composed_config_sha256':w.canonical_sha(config),
        'resolved_config':resolved,'expected_runtime':expected}


def verify_sources(plan):
    w.require(plan['source']==plan['scientific_source'],'single adopted N36 source across four arms')
    closure.verify_source(plan['worktree'],plan['source'])
    w.require(source_paths(plan['worktree']) <= {x['path'] for x in plan['source']['files']},'N36 source closure incomplete')


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


_ENGINEERING_ROUTES = ('hydra.run.dir', 'main.eds_eval.output_dir',
                       'main.eds_eval.report_dir', 'main.eds_mechanism_pretest.output_dir')
_ENGINEERING_IDENTITIES = ('main.eds_eval.job_id', 'main.eds_mechanism_pretest.run_id')


def engineering_command(plan, runtime, row, *, audit=None):
    """Map the audited C0 command; only two identity and four output overrides."""
    from scripts.qd_ed_n36_engineering_api import for_plan
    engineering = for_plan(plan)
    audit = engineering.read(plan['audit_plan']) if audit is None else audit
    audited_row = engineering.audit_mapping(plan, audit, row)
    argv, _ = command(audit, runtime, audited_row)
    output = Path(plan['artifact_root']) / 'attempts' / row['episode_key']
    destinations = (output, output / 'eds_eval', Path(plan['artifact_root']) / 'reports', output / 'mechanism')
    replacements = {key: str(value) for key, value in zip(_ENGINEERING_ROUTES, destinations)}
    replacements.update({key: row['episode_key'] for key in _ENGINEERING_IDENTITIES})
    for key, value in replacements.items():
        w.require(sum(arg.startswith(key + '=') for arg in argv) == 1,
                  'engineering command exact override coverage')
        argv = [key + '=' + runner.hydra(value) if arg.startswith(key + '=') else arg for arg in argv]
    return argv, output


def engineering_manifest(plan, runtime, row, *, audit=None):
    from scripts.qd_ed_n36_engineering_api import for_plan
    engineering = for_plan(plan)
    audit = engineering.read(plan['audit_plan']) if audit is None else audit
    audited_row = engineering.audit_mapping(plan, audit, row)
    original = manifest(audit, runtime, audited_row)
    argv, output = engineering_command(plan, runtime, row, audit=audit)
    config, resolved = compose_launch(argv, plan['worktree'])
    original_config, _ = compose_launch(original['argv'], plan['worktree'])
    # Production Hydra recomposition must be identical after reversing only the
    # six authorized operational changes. No scientific override is exempted.
    normalized = copy.deepcopy(config)
    for key in (*_ENGINEERING_ROUTES, *_ENGINEERING_IDENTITIES):
        # Hydra consumes hydra.run.dir; its exact argv replacement is checked
        # above, and it is absent from the returned application config.
        if key == 'hydra.run.dir':
            continue
        path = key.split('.')
        target, prior = normalized, original_config
        for part in path[:-1]:
            target, prior = target[part], prior[part]
        target[path[-1]] = prior[path[-1]]
    engineering.exact(normalized, original_config, 'engineering scientific config equivalence')
    normalized_resolved = copy.deepcopy(resolved)
    for key in ('output_dir', 'run_id'):
        normalized_resolved['mechanism_pretest'][key] = original['resolved_config']['mechanism_pretest'][key]
    engineering.exact(normalized_resolved, original['resolved_config'], 'engineering resolved C0 config')
    return {'schema': 'n36-engineering-runtime-v1', 'cohort': engineering.IDENTITY,
            'purpose': engineering.PURPOSE, 'scope': plan['scope'], 'accounting': plan['accounting'],
            'deployment': plan['deployment'], 'audit_plan': plan['audit_plan'],
            'audit_row': audited_row, 'audit_manifest': audit['expected_manifests'][audited_row['episode_key']],
            'scientific_eligible': False, 'matched_improvement_eligible': False, 'promotion_eligible': False,
            'row': row, **{key: plan[key] for key in ('source', 'scientific_source', 'native_build',
                'runtime', 'runtime_closure', 'controller_semantics')},
            'argv': argv, 'output_dir': str(output), 'composed_config_sha256': w.canonical_sha(config),
            'resolved_config': resolved, 'expected_runtime': original['expected_runtime']}


def verify_engineering_manifest(reference, plan, runtime, row, *, audit=None):
    actual = w.read_ref(reference)
    expected = engineering_manifest(plan, runtime, row, audit=audit)
    w.require(actual == json.loads(json.dumps(expected)), 'engineering external manifest differs')
    return actual
