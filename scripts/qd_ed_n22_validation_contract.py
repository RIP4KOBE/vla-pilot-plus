#!/usr/bin/env python3
"""Closed N22 validation; scientific bytes and Codex/E2 provider remain frozen."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]
SESSION = ROOT.parent if ROOT.name == 'study_worktree' else ROOT.parents[2]
RUN_DIR = SESSION / 'variants/n22_hold_conditioned_lift'
DEV_PLAN = RUN_DIR / 'plan.frozen.v1.gpu7.json'
VALIDATION_PLAN = RUN_DIR / 'validation-plan.frozen.v1.gpu7.json'
DEV_COMMIT = '60425750c41c8a46e1102e02e2e4e4d2f97fb242'
DEV_PLAN_SHA = '30846268778c46f2d9ad25a92abe7869395d3ead218da1a97dbf24fae4d07218'
DEV_STATUS = RUN_DIR / 'execution/supervisor-status-gpu7-v1.json'
PROTOCOL = RUN_DIR / 'protocol-validation-conditional-v1.md'
PROTOCOL_SHA = 'b2e94ebd3a79495a6a12db052ddd8ca6db764f65b2632fa092c31d593cd7c51b'
DEV_REVIEW = RUN_DIR / 'validation-dev-promotion-review-v1.json'
DEV_RESULT = RUN_DIR / 'result-v1.json'
DEV_READER = RUN_DIR / 'summarize_cohort_cpu_v1.py'
SOURCE_REVIEW = RUN_DIR / 'validation-source-review-v1.json'
COHORT = 'N22_VALIDATION_20260930'
DEV_COHORT = 'N22_HOLD_LIFT_DEV_20260930'
ARMS = ('C0','Q0','N22')
LIMITS = {'dispatches':60,'gpu_hours':32.,'episode_timeout_seconds':1800,'cleanup_seconds':40,'physical_gpu':7}
GPU7_UUID = 'GPU-48473162-9548-1a19-04aa-ea86c5349187'
GPU7_PROOF = 'rdt-qd-ed-final-20260921T093925Z__gpu7_cuda_egl__4fafff3673e5'
HISTORY_SHA = '304c99c7f6df75a68c3278df0640c6a5bb744d04b2457d5991881e9ac4b2b573'
FIELDS = ('task_id','env_seed','policy_seed','init_index','init_row_sha256','init_file_sha256','bddl_sha256')
ADDITIONS = {'scripts/qd_ed_n22_validation_contract.py','scripts/qd_ed_n22_validation_prepare.py',
 'scripts/qd_ed_n22_validation_supervise.py','scripts/qd_ed_n22_validation_report.py',
 'tests/test_qd_ed_n22_validation.py','experiments/iteration_022_hold_lift/protocol-validation-conditional-v1.md',
 'experiments/iteration_022_hold_lift/validation-runtime-contract-v1.md'}
ALLOWED_MODIFIED = {'scripts/qd_ed_final_runner.py'}
_SCOPE = None


def require(ok,message):
    if not ok: raise ValueError(message)


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(path): return {'path':str(Path(path).resolve()),'sha256':sha(path)}
def read(path): return json.loads(Path(path).read_text())
def read_ref(v):
    require(isinstance(v,dict) and set(v)=={'path','sha256'} and Path(v['path']).is_absolute()
            and sha(v['path'])==v['sha256'],'validation reference missing/changed')
    return read(v['path'])


def source_record(root,parent):
    root=Path(root);head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    original={x['path']:x['sha256'] for x in parent['code_files']}
    paths=set(original)|ADDITIONS
    rows=[]
    for name in sorted(paths):
        path=root/name;require(path.is_file() and not path.is_symlink(),'validation source missing/linked')
        require(path.read_bytes()==subprocess.check_output(['git','show',head+':'+name],cwd=root),'validation uncommitted source')
        rows.append({'path':name,'sha256':sha(path)})
    unchanged=all(v['sha256']==original[v['path']] for v in rows if v['path'] in original and v['path'] not in ALLOWED_MODIFIED)
    require(unchanged and parent['source_commit']==DEV_COMMIT,'validation changed frozen scientific/provider/main/audit bytes')
    # A tracked edit outside the expressly permitted evaluation delta is rejected too.
    changed=set(subprocess.check_output(['git','diff','--name-only',DEV_COMMIT,head],cwd=root,text=True).splitlines())
    require(changed <= ADDITIONS|ALLOWED_MODIFIED,'validation source delta exceeds evaluation allowlist')
    require(sha(root/'experiments/iteration_022_hold_lift/protocol-validation-conditional-v1.md')==PROTOCOL_SHA,
            'validation protocol copy differs')
    return {'commit':head,'files':rows,'changed_paths':sorted(changed),'scientific_unchanged':True}


def dev_promotion(root,r):
    """Only exposed Dev outcomes are inspected here, never protected outcomes."""
    require(sha(DEV_PLAN)==DEV_PLAN_SHA,'frozen N22 Dev plan bytes differ')
    review=read(DEV_REVIEW);parent=read(DEV_PLAN)
    require(set(review)=={'schema','disposition','dev_plan','dev_status','dev_result','cell_audits','allow_validation'}
        and review['schema']=='n22-dev-promotion-review-v1' and review['disposition']=='promoted'
        and review['allow_validation'] is True and review['dev_plan']==ref(DEV_PLAN) and review['dev_status']==ref(DEV_STATUS), 'N22 Dev root promotion review missing')
    status=read_ref(review['dev_status']);rows=parent['episodes'];result=read_ref(review['dev_result'])
    require(review['dev_result']==ref(DEV_RESULT) and result.get('schema')=='n22-dev-cohort-result-v1'
        and result.get('cohort_id')==DEV_COHORT and result.get('source_commit')==DEV_COMMIT
        and result.get('plan')==review['dev_plan'] and result.get('terminal_status')=={**review['dev_status'],'content':status}
        and result.get('decision')=='ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION' and result.get('dev_gate_promoted') is True
        and result.get('dispatched')==result.get('audited_cells')==result.get('planned')==40
        and result.get('cost_missing_fields')==[] and result.get('reader_sha256')==sha(DEV_READER),
        'N22 terminal result promotion/source/status differs')
    require(parent['source_commit']==DEV_COMMIT and len(rows)==40
        and status.get('status')=='completed_all_forty_audited' and status.get('dev_gate_promoted') is True
        and status.get('completed_keys')==[x['episode_key'] for x in rows], 'N22 actual complete Dev promotion required')
    events=r['read_events'](Path(root)/'data/attempt-ledger.jsonl')
    local=[e for e in events if e.get('identity',{}).get('iteration')==DEV_COHORT]
    require(len([e for e in local if e['event']=='dispatched'])==40
        and len({e['attempt_id'] for e in local})==40 and len(review['cell_audits'])==40,'N22 Dev must have exactly40 charged cells')
    require([v['episode_key'] for v in result['rows']]==[v['episode_key'] for v in rows], 'N22 terminal result row order differs')
    counts={a:0 for a in ('C0','Q0','N21','N22')}; guided=parents=0
    for row in rows:
        finals=[e for e in local if e.get('episode_key')==row['episode_key'] and e['event'] in r['TERMINAL']]
        require(len(finals)==1 and finals[0]['event']=='valid' and finals[0].get('outcome_valid') is True,'N22 Dev cell invalid/missing')
        final=finals[0]
        require(final.get('identity')==r['episode_identity'](row) and final.get('init_row_sha256')==row['init_row_sha256']
            and final.get('profile_manifest_sha256')==parent['profiles_sha256']
            and final.get('runtime_manifest_sha256')==parent['runtime_manifest_sha256']
            and final.get('runtime_inventory_sha256')==parent['runtime_inventory_sha256']
            and final.get('required_cost_telemetry_complete') is True,'N22 Dev cell identity/cost differs')
        matches=[a for a in review['cell_audits'] if a['attempt_id']==final['attempt_id']]
        require(len(matches)==1 and final['source_commit']==DEV_COMMIT and final['plan_sha256']==sha(DEV_PLAN), 'N22 Dev cell source association differs')
        require(matches[0]['report']['path']==str(Path(final['output_dir'])/'eds_eval/decision-evidence-audit.json'), 'N22 Dev audit path differs')
        rr=result['rows'][rows.index(row)]
        require(all(rr.get(k)==v for k,v in {'episode_key':row['episode_key'],'task_id':row['task_id'],
            'arm':row['profile'],'attempt_id':final['attempt_id'],'event':'valid','outcome_valid':True,
            'success':final['success'],'native_valid':True,'audit':matches[0]['report']}.items()),'N22 result cell association differs')
        audit=read_ref(matches[0]['report'])
        require(audit.get('accepted') is True and audit.get('evidence_complete') is True,'N22 Dev cell lacks accepted native audit')
        counts[row['profile']]+=int(final['success'] is True)
        if row['profile']=='N22':
            gate=audit.get('n22_hold_lift_quality_audit',{});selection=audit.get('n5_grasp_timing_audit',{})
            n=final.get('guided_chunks',-1)
            require(type(n) is int and n>=0 and final.get('candidate_evaluations')==176*n
                and final.get('score_batches')==11*n,'N22 Dev guided/canonical count missing/differs')
            if n:
                require(selection.get('checked_decisions')==n,'N22 Dev guided audit count differs')
                require(n>=0 and gate.get('score_batches_verified')==11*n and gate.get('candidate_scores_verified')==176*n
                    and selection.get('parent_rounds_verified')==10*n,'N22 Dev native compute/parent evidence differs')
                guided+=n;parents+=selection['parent_rounds_verified']
            else:require(not gate and not selection,'N22 Dev zero-guided audit differs')
    require(result['counts']=={a:{'audited':10,'success':n} for a,n in counts.items()},'N22 result aggregate counts differ')
    require(counts==status['successes'] and counts['N22']>=5 and counts['N22']>=max(counts[a] for a in ('C0','Q0','N21'))
        and guided>0 and parents>0 and status['native']['N22']['guided_decisions']==guided,
        'N22 Dev numeric/substantive promotion differs')
    return ref(DEV_REVIEW)


def review_source(source,parent):
    v=read(SOURCE_REVIEW)
    require(v=={'schema':'n22-validation-source-review-v1','disposition':'accepted','dev_plan':ref(DEV_PLAN),
        'protocol':ref(PROTOCOL),'source':source,'allowed_modified':sorted(ALLOWED_MODIFIED),
        'allowed_added':sorted(ADDITIONS),'runtime':{'path':parent['runtime_manifest_path'],'sha256':parent['runtime_manifest_sha256']},
        'no_execution_release':True},'validation root source review missing/differs')
    return ref(SOURCE_REVIEW)


def pair(v,key='env_seed'):
    p=(v.get('task_id'),v.get(key));require(all(type(x) is int for x in p),'validation identity task/seed missing');return p


def metadata(root,parent):
    """Project identity fields only; never inspect or return protected success values."""
    root=Path(root);seed_path=Path(parent['seed_plan_path'])
    require(sha(seed_path)==parent['seed_plan_sha256'],'frozen validation seeds changed')
    paths=[root/'data/historical-exposure-inventory.jsonl',root/'data/exposure-registry.jsonl',root/'data/attempt-ledger.jsonl']
    blobs=[p.read_bytes() for p in paths]
    require(hashlib.sha256(blobs[0]).hexdigest()==HISTORY_SHA,'frozen historical identity inventory changed')
    identities=[]
    for blob in blobs[:2]:
        rows=[]
        for line in blob.splitlines():
            v=json.loads(line)
            rows.append({'pair':pair(v,'episode_seed'),'attempt_id':v.get('attempt_id'),
                         'cohort_id':v.get('cohort_id')})
        identities.append(rows)
    ledger=[]
    for line in blobs[2].splitlines():
        v=json.loads(line)
        if v['event'] not in {'reserved','dispatched'}: continue
        i=v.get('identity',{})
        require(i.get('split') in {'dev','validation','formal'},'unknown dispatched identity scope')
        ledger.append({'event':v['event'],'attempt_id':v['attempt_id'],'pair':pair(i),
                       'iteration':i.get('iteration'),'profile':i.get('profile'),'split':i['split']})
    require(all(p.read_bytes()==blob for p,blob in zip(paths,blobs)),'metadata changed during identity snapshot')
    return read(seed_path),identities[0],identities[1],ledger,{'seed_plan':ref(seed_path),
        'inputs':[{'path':str(p.resolve()),'sha256':hashlib.sha256(blob).hexdigest()} for p,blob in zip(paths,blobs)],
        'protected_outcomes_read':False}


def first_unused(seeds,history,registry,ledger,*,allow_own=False):
    require(tuple(seeds['backend_task_order'])==tuple(range(10)),'frozen backend task order differs')
    own={v['attempt_id'] for v in ledger if v['iteration']==COHORT} if allow_own else set()
    require(not any(v['split']=='validation' and v['profile']=='N22' and v['attempt_id'] not in own for v in ledger),
            'N22 validation already reserved; one cohort only')
    require(not any(v['iteration']==COHORT for v in ledger) or allow_own,'N22 cohort already started')
    registered={tuple(v['pair']) for v in registry}
    old_dispatched={tuple(v['pair']) for v in ledger if v['split']=='validation' and v['event']=='dispatched' and v['attempt_id'] not in own}
    require(old_dispatched<=registered,'historical dispatched validation exposure registry needs reconciliation')
    used={tuple(v['pair']) for v in history}
    used|={tuple(v['pair']) for v in registry if not(v.get('cohort_id')==COHORT and v.get('attempt_id') in own)}
    used|={tuple(v['pair']) for v in ledger if v['attempt_id'] not in own}
    used|={pair(v) for name in ('dev','formal') for v in seeds['blocks'][name]}
    seen=set();first=None
    for c in range(1,5):
        rows=[]
        for b in (1,2):
            values=seeds['blocks'][f'validation_c{c}_b{b}']
            require(len(values)==10 and {v['task_id'] for v in values}==set(range(10)), 'validation block task map changed')
            require(all(type(v['policy_seed']) is int for v in values),'validation policy seed missing')
            rows+=values
        pairs={pair(v) for v in rows}
        require(len(pairs)==20 and not seen&pairs,'validation seeds duplicate');seen|=pairs
        if first is None and not pairs&used:first=f'c{c}'
    require(first is not None,'no untouched complete validation cohort remains')
    return first


def rows_for(seeds,cohort):
    require(cohort in {'c1','c2','c3','c4'},'invalid validation cohort selection')
    result=[]
    for b in (1,2):
        block=f'validation_{cohort}_b{b}';mapping={v['task_id']:v for v in seeds['blocks'][block]}
        for task in range(10):
            for arm in ARMS:
                result.append({**{k:mapping[task][k] for k in FIELDS},'split':'validation','seed_block':block,
                    'iteration':COHORT,'profile':arm,'budget_bucket':'validation','timeout_seconds':1800,
                    'episode_key':f'n22v_{cohort}_b{b}_t{task:02d}_{arm.lower()}_20260930'})
    return result


def require_budget_state(state,r):
    r['n22_support']().require_state(state,r)
    require(not state.get('external_resource_hold',{}).get('do_not_auto_resume',False),'validation external resource hold')
    a=state.get('n22_validation_authorization',{})
    require(set(a)=={'schema','cohort_id','seed_cohort','protocol_sha256','dev_review','source_review','run_once','physical_gpu'}
        and a['schema']=='n22-validation-authorization-v1' and a['cohort_id']==COHORT
        and a['seed_cohort'] in {'c1','c2','c3','c4'} and a['protocol_sha256']==PROTOCOL_SHA
        and a['run_once'] is True and a['physical_gpu']==7,'separate N22 validation authorization missing')


def validate_contract(plan,manifest,runtime,seeds,root,r):
    require(plan==read(VALIDATION_PLAN),'validation requires its exact frozen plan file')
    parent=read(DEV_PLAN);source=source_record(root,parent);meta=plan.get('n22_validation',{})
    require(sha(PROTOCOL)==PROTOCOL_SHA and meta.get('schema')=='n22-protected-validation-v1'
        and meta.get('cohort_id')==COHORT and meta.get('limits')==LIMITS
        and meta.get('protocol')==ref(PROTOCOL) and meta.get('dev_review')==dev_promotion(root,r)
        and meta.get('source_review')==review_source(source,parent), 'validation promotion/source/protocol gate differs')
    require(plan['source_commit']==source['commit'] and plan['code_files']==source['files']
        and plan.get('n22_cohort') is None and plan.get('n21_cohort') is None and set(plan['candidate_profiles'])=={'N22'}
        and plan['phase_authorization']=={'dev':False,'validation':True,'formal':False}
        and set(manifest['profiles'])==set(ARMS) and plan['episodes']==rows_for(seeds,meta['seed_cohort']), 'validation closed matrix/profile differs')
    for key in ('profiles_sha256','runtime_manifest_path','runtime_manifest_sha256','runtime_inventory_sha256','seed_plan_sha256'):
        require(plan[key]==parent[key],'validation scientific input/runtime fingerprint differs')
    require(plan['candidate_profiles']['N22']['sha256']==parent['candidate_profiles']['N22']['sha256']
        and runtime==read(parent['runtime_manifest_path']) and r['runtime_gpu'](runtime)==7
        and runtime['gpu_mapping']['uuid']==GPU7_UUID and runtime['gpu_mapping']['egl_device_index']==4
        and runtime['cuda_egl_verified'] is True and runtime['cuda_egl_probe']['resource_id']==GPU7_PROOF
        and runtime['frozen_stage_provider']['backend']=='codex_cli'
        and runtime['stage_recovered_error_condition']==r['E2_STAGE_CONDITION'], 'validation Codex/E2/GPU7 runtime changed')
    m=metadata(root,parent);require(first_unused(*m[:4],allow_own=True)==meta['seed_cohort'],'validation cohort no longer first untouched cohort')
    state=r['read_state'](Path(root)/'research-state.yaml');require_budget_state(state,r)
    auth=state['n22_validation_authorization']
    require(auth['seed_cohort']==meta['seed_cohort'] and auth['dev_review']==meta['dev_review']
        and auth['source_review']==meta['source_review'],'validation separate authorization differs from frozen plan')


@contextmanager
def supervised_scope(plan,root,key):
    global _SCOPE
    require(_SCOPE is None,'nested validation supervisor')
    _SCOPE=(str(Path(root).resolve()),plan['source_commit'],key,os.getpid(),threading.get_ident())
    try:yield
    finally:_SCOPE=None


def require_scope(plan,root,r,row=None):
    require(_SCOPE is not None and _SCOPE[0]==str(Path(root).resolve()) and _SCOPE[1]==plan['source_commit']
        and _SCOPE[3:]==(os.getpid(),threading.get_ident()) and (row is None or row['episode_key']==_SCOPE[2]),'validation requires one-cell supervisor')


def protected_budget(state,events,resources,row,timeout,r,*,plan):
    require_budget_state(state,r)
    require(row in plan['episodes'] and row['iteration']==COHORT and row['budget_bucket']==row['split']=='validation'
        and timeout==1800,'validation row/bucket/timeout differs')
    local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    dispatched=[e for e in local if e['event']=='dispatched'];spent=sum(e.get('gpu_process_wall_seconds',0.) for e in local if e['event'] in r['TERMINAL'])
    snap=r['budget_snapshot'](events,resources);remaining=60-len(dispatched)
    require(snap['running']==snap['gpu_healthcheck_inflight']==0 and all(g[-1]['event'] in r['TERMINAL'] for g in r['event_groups'](events).values()),'validation unfinished owned work')
    require(len(dispatched)<60 and spent+1840<=32*3600,'validation local attempts/hours exhausted')
    formal_attempts=max(0,40-snap['by_bucket']['formal']);formal_hours=max(0.,12.-snap['gpu_hours_by_bucket']['formal'])
    require(snap['by_bucket']['validation']+remaining<=180 and snap['dispatched']+remaining+formal_attempts<=438,
            'validation full matrix would consume formal attempt reserve')
    require(snap['gpu_hours_consumed']+max(0.,32-spent/3600)+formal_hours<=100.+1e-9,
            'validation entire local ceiling cannot fit formal GPU reserve')


def admission(plan,runtime,row,events,resources,root,r):
    index=plan['episodes'].index(row);local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
    require(not any(e.get('episode_key')==row['episode_key'] for e in local),'validation no retry or replacement')
    prefix=plan['episodes'][:index];require(all(e.get('episode_key') in {v['episode_key'] for v in prefix} for e in local),'validation exact prefix required')
    for prior in prefix:
        finals=[e for e in local if e.get('episode_key')==prior['episode_key'] and e['event'] in r['TERMINAL']]
        require(len(finals)==1 and finals[0]['event']=='valid' and finals[0].get('outcome_valid') is True,'validation invalid predecessor stops cohort')
        checkpoint=read(Path(finals[0]['output_dir'])/'eds_eval/n22-validation-cell-audit.json')
        verify_checkpoint(checkpoint,finals[0],prior,plan,r)
    return {'n22_validation_cohort_id':COHORT,'n22_validation_seed_block':row['seed_block'],
            'n22_validation_protocol_sha256':PROTOCOL_SHA}


def verify_checkpoint(checkpoint,final,row,plan,r):
    """Bind CPU audit bytes to the exact charged native attempt and frozen row."""
    require(final.get('identity')==r['episode_identity'](row) and final.get('source_commit')==plan['source_commit']
        and type(final.get('success')) is bool and final.get('required_cost_telemetry_complete') is True
        and final.get('init_row_sha256')==row['init_row_sha256']
        and final.get('plan_sha256')==sha(VALIDATION_PLAN)
        and final.get('profile_manifest_sha256')==plan['profiles_sha256']
        and final.get('runtime_manifest_sha256')==plan['runtime_manifest_sha256']
        and final.get('runtime_inventory_sha256')==plan['runtime_inventory_sha256'],
        'protected terminal identity/cost mismatch')
    expected={'schema':'n22-validation-cell-audit-v1','accepted':True,'attempt_id':final['attempt_id'],
        **{k:row[k] for k in ('episode_key','profile','seed_block',*FIELDS)},
        'source_commit':plan['source_commit'],'plan_sha256':final['plan_sha256'],'success':final['success'],
        'guided_chunks':final['guided_chunks']}
    require(all(checkpoint.get(k)==v for k,v in expected.items()),'protected checkpoint identity mismatch')
    native=Path(final['output_dir'])/'eds_eval/decision-evidence-audit.json'
    require(checkpoint.get('native_report')==ref(native),'protected native report association differs')
    report=read_ref(checkpoint['native_report'])
    require(report.get('accepted') is True and report.get('evidence_complete') is True,'protected native report hash/acceptance differs')
    if row['profile']=='N22':
        n=final['guided_chunks'];gate=report.get('n22_hold_lift_quality_audit',{});selection=report.get('n5_grasp_timing_audit',{})
        require(type(n) is int and n>=0 and final.get('candidate_evaluations')==176*n and final.get('score_batches')==11*n
            and ((n==0 and not gate and not selection) or (gate.get('candidate_scores_verified')==176*n
            and gate.get('score_batches_verified')==11*n and selection.get('checked_decisions')==n
            and selection.get('parent_rounds_verified')==10*n)),'protected checkpoint native compute differs')
    return report


def register_dispatch(root,event):
    """Journal-first exposure metadata; caller owns state lock, no outcome read."""
    if event.get('event')!='dispatched' or event.get('identity',{}).get('iteration')!=COHORT:return
    path=Path(root)/'data/exposure-registry.jsonl';i=event['identity']
    value={'schema':'n22-validation-dispatch-exposure-v1','cohort_id':COHORT,'attempt_id':event['attempt_id'],
        'task_id':i['task_id'],'episode_seed':i['env_seed'],'policy_seed':i['policy_seed'],
        'seed_block':event['n22_validation_seed_block'],'init_row_sha256':event['init_row_sha256'],
        'study_role':'validation','exposure_kind':'actual_dispatch','outcomes_read':False}
    with path.open('a') as stream:
        stream.write(json.dumps(value,sort_keys=True)+'\n');stream.flush();os.fsync(stream.fileno())
