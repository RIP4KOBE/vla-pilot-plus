#!/usr/bin/env python3
"""Read-only three-mode evidence aggregation, outside the frozen runtime.

Running cohorts remain partial. Final acceptance also requires a fresh CPU-only
--no-write audit of each completed cohort. All outputs must be outside raw runs.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import yaml

MODES=('eds','vls','eds_qd')
TASKS=list(range(10))
SEEDS=[44,235,43,546,6,621,197,87,151,548]
PATH_EXCLUSIONS=('hydra.run.dir','main.eds_eval.job_id','main.episode_rng_fixture_manifest',
    'perception.vlm_agent.query_template_dir','policy.rdt.pretrained_path',
    'policy.rdt.text_encoder','policy.rdt.vision_encoder')
METHOD_EXCLUSIONS=('steering.method','main.guidance_type','main.eds_eval.method_label',
    'main.eds_config.qd_archive_mode','main.eds_config.qd_parent_sampling',
    'main.eds_config.qd_metrics_observer','main.eds_mechanism_pretest.enabled',
    'main.vls_config.sample_batch_size','main.vls_config.guide_scale','main.vls_config.diversity_scale',
    'backend.libero.task_guide_scales')
COMPUTE_KEYS=('model_forward_calls','model_batch_rows','denoising_invocations','model_denoising_steps',
    'denoising_step_batch_rows','renoise_invocations','reward_calls','reward_evaluations','reward_scoring_batches',
    'guided_chunks','unguided_chunks','rbf_gradient_calls','rbf_gradient_batch_rows',
    'vision_encoder_forward_calls','vision_encoder_batch_rows','text_encoder_forward_calls','text_encoder_batch_rows',
    'dino_forward_calls','dino_batch_rows','provider_logical_call_attempts','provider_completed_turns',
    'provider_failed_calls','provider_input_tokens','provider_cached_input_tokens','provider_output_tokens',
    'provider_reasoning_output_tokens','provider_call_latency_s','stage_codex_logical_call_attempts',
    'stage_codex_completed_turns','stage_codex_failed_calls','stage_codex_call_latency_s',
    'guidance_codex_logical_call_attempts','guidance_codex_completed_turns','guidance_codex_failed_calls',
    'guidance_codex_call_latency_s')

def sha(data): return hashlib.sha256(data).hexdigest()
def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def identity(value): return sha(canonical(value))
def read_json(path): return json.loads(Path(path).read_bytes())
def finite(value): return type(value) in (float,int) and math.isfinite(value)
def safe_path(root,value):
    path=Path(value);result=(path if path.is_absolute() else root/path).resolve()
    if not result.is_relative_to(root.resolve()): raise ValueError('Evidence path escapes run')
    return result

def strip_config(value,fields):
    result=deepcopy(value)
    for field in fields:
        node=result;parts=field.split('.')
        for part in parts[:-1]:
            if part not in node: break
            node=node[part]
        else: node.pop(parts[-1],None)
    return result

def merged(base,changes):
    result=deepcopy(base)
    for key,value in changes.items():
        result[key]=merged(result[key],value) if isinstance(value,dict) else deepcopy(value)
    return result

def method_protocol_valid(folder,manifest,config):
    expected=yaml.safe_load((folder/'source/configs/evaluation/libero_object_swap.yaml').read_bytes())
    profile=yaml.safe_load((folder/f"source/configs/steering/{manifest['method']}.yaml").read_bytes())
    expected=merged(expected,profile)
    expected['main'].update(episode_num=10,episode_start_index=0,episode_seed_schedule=SEEDS)
    expected['backend']['libero']['task_ids_filter']=TASKS
    expected['steering']['method']=manifest['method']
    expected['main']['eds_eval']['method_label']=manifest['method']
    return strip_config(expected,PATH_EXCLUSIONS)==strip_config(config,PATH_EXCLUSIONS)

def sum_known(rows,key):
    values=[r.get(key) for r in rows]
    known=[v for v in values if finite(v)]
    return dict(total=sum(known) if len(known)==len(values) and values else None,
                observed_subtotal=sum(known),known_rows=len(known),unknown_rows=len(values)-len(known))

def rows_snapshot(path,artifacts,issues):
    if not path.exists(): return []
    data=path.read_bytes();artifacts[str(path)]=dict(sha256=sha(data),bytes=len(data))
    result=[];lines=data.splitlines()
    for number,line in enumerate(lines,1):
        if not line.strip():continue
        try:
            value=json.loads(line)
            if not isinstance(value,dict):raise ValueError('Expected object')
            result.append(value)
        except (ValueError,TypeError):
            issues.append(dict(path=str(path),line=number,trailing_partial=(number==len(lines) and not data.endswith(b'\n'))))
    return result

def mechanism_counts(rows,mode):
    result={'recorded_chunks':len(rows),'guided_select_action_latency_s':sum_known(rows,'select_action_latency_s')}
    if mode=='vls':
        for key in ('model_forward_calls','model_batch_rows','reward_calls','reward_evaluations','reward_scoring_batches','rbf_gradient_calls'):
            result['guided_'+key]=sum_known([r.get('compute_delta',{}) for r in rows],key)
        for family in ('gradient','rbf'):
            result[family]={key:sum_known([r.get(family,{}) for r in rows],key) for key in ('attempted','applied','zero','nonfinite','exception','unavailable')}
        result['fkd']={key:sum_known([r.get('fkd',{}).get('diagnostics') or {} for r in rows],key) for key in ('calls','score_opportunities','actual_resamples','ess_skips')}
        result['selection_sources']=dict(Counter(r.get('selection',{}).get('source','missing') for r in rows))
    else:
        for key in ('score_call_count','search_evaluation_count','qd_evaluation_count','initial_diversity_steps','rollout_diversity_iters_applied'):
            result[key]=sum_known(rows,key)
        result['archive_enabled_chunks']=sum(r.get('qd_archive_enabled') is True for r in rows)
        result['archive_active_chunks']=sum(r.get('qd_archive_active_for_chunk') is True for r in rows)
        result['parent_sources']=dict(sum((Counter(r.get('parent_count_by_source',{})) for r in rows),Counter()))
        result['final_selection_sources']=dict(Counter(r.get('selected_parent_source','missing') for r in rows))
        coverages=[r.get('qd_coverage_ratio_by_iter',[])[-1] for r in rows if r.get('qd_coverage_ratio_by_iter')]
        result['final_coverage']=dict(count=len(coverages),minimum=min(coverages) if coverages else None,maximum=max(coverages) if coverages else None,mean=sum(coverages)/len(coverages) if coverages else None)
    return result

def stage_counts(rows):
    queries=[r for r in rows if r.get('query_status') in ('ok','error')]
    return dict(boundaries=len(rows),queries=len(queries),successful_queries=sum(r.get('query_ok') is True for r in queries),
        query_errors=sum(r.get('query_status')=='error' or r.get('query_ok') is False for r in queries),
        guided_boundaries=sum(r.get('guidance_after') is True for r in rows),
        unguided_boundaries=sum(r.get('guidance_after') is False for r in rows),
        recorded_logical_attempts=sum_known(queries,'codex_logical_call_attempts'),
        recorded_completed_turns=sum_known(queries,'codex_completed_turns'),
        recorded_failed_calls=sum_known(queries,'codex_failed_calls'),
        query_latency_s=sum_known(queries,'query_latency_s'))

def detail_integrity(folder,audit):
    checks={};artifacts={}
    tasks=audit.get('tasks',[])
    checks['exact_task_rows']=[r.get('task_id') for r in tasks]==TASKS and [r.get('seed') for r in tasks]==SEEDS
    checks['all_task_rows_valid']=len(tasks)==10 and all(r.get('valid') is True for r in tasks)
    for row in tasks:
        task=row.get('task_id');record=row.get('extended_contract',{});valid=False
        try:
            p=safe_path(folder,record['path']);data=p.read_bytes();report=json.loads(data)
            valid=(record.get('written') is True and record.get('hash_encoding')=='file_bytes'
                and record.get('valid') is True and sha(data)==record.get('sha256')
                and report.get('task_contract_valid') is True and report.get('task_evidence_complete') is True
                and report.get('task_id')==task)
            artifacts[str(p)]=dict(sha256=sha(data),bytes=len(data))
        except (KeyError,ValueError,OSError,TypeError): pass
        checks[f'task_{task}_contract_report']=valid
    record=audit.get('method_audit',{});valid=False
    try:
        p=safe_path(folder,record['path']);data=p.read_bytes();report=json.loads(data);chunks=report['chunks']
        valid=(record.get('valid') is True and record.get('written') is True
               and record.get('hash_encoding')=='file_bytes' and sha(data)==record.get('sha256')
               and record.get('chunks')==len(chunks)>0 and record.get('failed_chunks')==0
               and all(r.get('stage_binding_valid') is True and r.get('recorded_mechanism_valid') is True for r in chunks)
               and report.get('method')==audit.get('method'))
        artifacts[str(p)]=dict(sha256=sha(data),bytes=len(data))
    except (KeyError,ValueError,OSError,TypeError):pass
    checks['method_chunk_report']=valid
    return checks,artifacts

def audit_projection(report):
    fields=('schema','method','scope','full_audit_performed','valid','checks','errors','completed','planned','successes',
            'success_task_ids','stage_queries','infrastructure_error_episodes','evaluation_directory')
    projected={k:report.get(k) for k in fields}
    projected['tasks']=[{**{k:r.get(k) for k in ('task_id','episode','seed','valid','success','reward_contract_valid','videos')},
        'extended_contract':{k:r.get('extended_contract',{}).get(k) for k in ('valid','summary')}} for r in report.get('tasks',[])]
    projected['method_audit']={k:report.get('method_audit',{}).get(k) for k in ('valid','chunks','failed_chunks')}
    return projected


def fresh_audit(folder,manifest):
    """Only launch the content-bound offline auditor, never a worker/model entry."""
    code_root=Path(manifest['code_root']);script=code_root/'scripts/audit_steering.py'
    expected=manifest['source_sha256']['scripts/audit_steering.py']
    dependencies={relative:expected_hash for relative,expected_hash in manifest['source_sha256'].items() if relative.endswith('.py')}
    for relative,expected_hash in dependencies.items():
        path=safe_path(code_root,relative)
        if sha(path.read_bytes())!=expected_hash:raise ValueError('Current audit dependency differs from frozen source: '+relative)
    config=yaml.safe_load((folder/'resolved-config.yaml').read_bytes())
    rng_manifest=Path(config['main']['episode_rng_fixture_manifest'])
    if sha(rng_manifest.read_bytes())!=config['main']['episode_rng_fixture_manifest_sha256']:
        raise ValueError('Current RNG fixture manifest differs from frozen configuration')
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1')
    result=subprocess.run([sys.executable,str(script),str(folder),'--no-write'],cwd=code_root,env=env,
                          capture_output=True,text=True,timeout=600)
    report=json.loads(result.stdout)
    return dict(exit_code=result.returncode,valid=result.returncode==0 and report.get('valid') is True,
                auditor_sha256=expected,current_python_dependencies_checked=len(dependencies),rng_manifest_sha256=sha(rng_manifest.read_bytes()),stdout_sha256=sha(result.stdout.encode()),stderr_sha256=sha(result.stderr.encode()),report=report)

def audit_finished_gate(status,manifest,audit):
    return dict(finished=status.get('state')=='finished',exit_zero=status.get('exit_code')==0,
        source_unchanged=status.get('source_unchanged') is True,
        full_v2_audit=audit.get('schema')=='steering_cohort_audit_v2' and audit.get('scope')=='full_v2_contract_and_recorded_method_evidence'
            and audit.get('full_audit_performed') is True and audit.get('valid') is True,
        all_audit_checks=bool(audit.get('checks')) and all(v is True for v in audit.get('checks',{}).values()),
        audit_task_window=audit.get('planned')==audit.get('completed')==10 and manifest.get('tasks')==TASKS and manifest.get('seeds')==SEEDS,
        audit_method=audit.get('method')==manifest.get('method'))

def inspect_run(folder,mode,now,revalidator=fresh_audit):
    artifacts={};issues=[];checks={};fresh=None
    def read(name,yml=False):
        p=folder/name;data=p.read_bytes();artifacts[str(p)]=dict(sha256=sha(data),bytes=len(data))
        return yaml.safe_load(data) if yml else json.loads(data)
    manifest=read('manifest.json');status=read('status.json');config=read('resolved-config.yaml',True)
    environment=read('environment.json');local=read('local-config.yaml',True)
    progress=read('progress.json') if (folder/'progress.json').exists() else {}
    evaluation=safe_path(folder,manifest['evaluation_directory'])
    streams={name:rows_snapshot(evaluation/(name+'.jsonl'),artifacts,issues) for name in
             ('episode_metadata','episode_compute','stage_events','eds_metrics','vls_metrics','phase_timing','safety_events')}
    metadata=streams['episode_metadata'];compute=streams['episode_compute'];stages=streams['stage_events']
    metrics=streams['vls_metrics' if mode=='vls' else 'eds_metrics']
    def check(key,value):checks[key]=bool(value)
    check('v2_method_identity',manifest.get('schema')=='steering_cohort_v2' and manifest.get('method')==mode and manifest.get('evaluation_directory')=='output/evaluation')
    check('task_seed_protocol',manifest.get('tasks')==TASKS and manifest.get('seeds')==SEEDS)
    check('config_hash',artifacts[str(folder/'resolved-config.yaml')]['sha256']==manifest.get('config_sha256'))
    check('environment_hash',artifacts[str(folder/'environment.json')]['sha256']==manifest.get('environment_sha256'))
    check('local_config_hash',artifacts[str(folder/'local-config.yaml')]['sha256']==manifest.get('local_config_sha256'))
    check('device_binding',manifest.get('physical_gpu')==local.get('gpu') and manifest.get('egl_device_id')==local.get('egl_device_id'))
    check('frozen_profile',method_protocol_valid(folder,manifest,config))
    source=manifest.get('source_sha256',{});source_bad=[]
    for relative,expected in source.items():
        try:
            p=safe_path(folder/'source',relative)
            if sha(p.read_bytes())!=expected:source_bad.append(relative)
        except (ValueError,OSError):source_bad.append(relative)
    check('source_snapshot',bool(source) and not source_bad)
    check('provider_contract',manifest.get('provider')=='codex_cli' and manifest.get('model')=='gpt-6-astra'
          and manifest.get('reasoning_effort')=='low' and manifest.get('fresh_reward') is True and manifest.get('online_stage') is True)
    check('asset_receipts_valid',environment.get('model_assets',{}).get('valid') is True and environment.get('rng',{}).get('valid') is True
          and environment.get('libero',{}).get('valid') is True and environment.get('libero_paths',{}).get('valid') is True)
    audit=read('audit.json') if (folder/'audit.json').exists() else {}
    gates=audit_finished_gate(status,manifest,audit)
    details={}
    if audit:
        details,more=detail_integrity(folder,audit);artifacts.update(more)
    finished=status.get('state')=='finished'
    if finished and all(checks.values()) and all(gates.values()) and details and all(details.values()):
        try:fresh=revalidator(folder,manifest)
        except Exception as exc:fresh=dict(valid=False,error_type=type(exc).__name__,error=str(exc))
    gates['persisted_detail_reports_valid']=bool(details) and all(details.values())
    gates['fresh_read_only_audit_valid']=fresh is not None and fresh.get('valid') is True and fresh.get('report',{}).get('full_audit_performed') is True
    fresh_report=fresh.get('report',{}) if fresh else {}
    gates['persisted_fresh_semantic_agreement']=bool(fresh_report) and audit_projection(audit)==audit_projection(fresh_report)
    gates['method_detail_matches_fresh_reconstruction']=False
    if fresh_report:
        try:
            method_record=audit['method_audit'];detail=read_json(safe_path(folder,method_record['path']))
            fresh_record=fresh_report['method_audit']
            gates['method_detail_matches_fresh_reconstruction']=(fresh_record.get('hash_encoding')=='canonical_json'
                and fresh_record.get('written') is False and identity(detail)==fresh_record.get('sha256'))
        except (KeyError,ValueError,OSError,TypeError):pass
    effective_audit=fresh_report if fresh and fresh.get('valid') is True else audit
    if finished:gates['no_partial_or_malformed_jsonl']=not issues
    accepted=all(checks.values()) and all(gates.values())
    state='accepted' if accepted else ('rejected' if finished and audit else ('awaiting_audit' if finished else 'partial'))
    task_rows=[]
    for episode,(task,seed) in enumerate(zip(TASKS,SEEDS)):
        c=[r for r in compute if r.get('episode_id')==episode and r.get('task_id')==task]
        st=[r for r in stages if r.get('episode_id')==episode and r.get('task_id')==task]
        mm=[r for r in metrics if r.get('episode',r.get('episode_id'))==episode and r.get('task_id')==task]
        action=[r for r in streams['safety_events'] if r.get('episode')==episode and r.get('task_id')==task and r.get('raw_action') is not None]
        ep=folder/'output'/f'episode_{episode+1}';videos=sorted(ep.glob('*agentview.mp4')) if ep.exists() else []
        completed=len(c)==1 and c[0].get('outcome')=='completed'
        ar=[r for r in effective_audit.get('tasks',[]) if r.get('task_id')==task]
        success=((ar[0].get('success') if len(ar)==1 else (('_success' in videos[0].name) if len(videos)==1 else None)) if completed else None)
        persisted_task=[r for r in audit.get('tasks',[]) if r.get('task_id')==task]
        phase=[r for r in streams['phase_timing'] if r.get('episode')==episode and r.get('event')=='exit']
        phase_names=sorted(set(r.get('name') for r in phase if isinstance(r.get('name'),str)))
        task_rows.append(dict(task_id=task,seed=seed,episode=episode,completed=completed,
            success=success,contract_valid=(ar[0].get('extended_contract',{}).get('valid') if len(ar)==1 else None),
            accepted=accepted and completed,episode_outcome=c[0].get('outcome') if len(c)==1 else None,
            stage=stage_counts(st),mechanism=mechanism_counts(mm,mode),executed_action_rows=len(action),
            compute={k:sum_known(c,k) for k in COMPUTE_KEYS},
            phase_timings_s={name:sum_known([r for r in phase if r.get('name')==name],'elapsed_s') for name in phase_names},
            videos=[str(v) for v in videos],contract_report=persisted_task[0].get('extended_contract') if len(persisted_task)==1 else None,
            fresh_contract_summary=ar[0].get('extended_contract',{}).get('summary') if fresh_report and len(ar)==1 else None))
    start=datetime.fromisoformat(status['started_at']);end=datetime.fromisoformat(status['completed_at']) if status.get('completed_at') else now
    assets=environment.get('model_assets',{})
    common=dict(commit=manifest.get('commit'),source_sha256=source,
        model_identity={k:assets.get(k) for k in ('expected_manifest_sha256','verifier_sha256','files_checked','bytes_hashed','files','normalization_files','normalization_checked')},
        rng={k:environment.get('rng',{}).get(k) for k in ('sha256','fixture_count')},
        libero={k:environment.get('libero',{}).get(k) for k in ('manifest_sha256','upstream_commit','files_verified')},
        imported_packages={name:{k:v.get(k) for k in ('module_version','sha256')} for name,v in environment.get('imported_packages',{}).items()},
        submodules=environment.get('submodules'),codex_cli=environment.get('codex_cli'),
        local_nonpath={k:v for k,v in local.items() if k not in ('gpu','egl_device_id','rdt_checkpoint','text_encoder','vision_encoder','libero_root','libero_config','torch_home')},
        shared_protocol=strip_config(config,PATH_EXCLUSIONS+METHOD_EXCLUSIONS),
        manifest_protocol={k:manifest.get(k) for k in ('tasks','seeds','provider','model','reasoning_effort','fresh_reward','online_stage','evaluation_directory')})
    result=dict(method=mode,run_dir=str(folder),state=state,accepted=accepted,manifest_commit=manifest.get('commit'),
        checks=checks,final_gates=gates,detail_checks=details,source_mismatches=source_bad,stream_issues=issues,
        worker_status=status,progress=progress,physical_gpu=manifest.get('physical_gpu'),egl_device_id=manifest.get('egl_device_id'),gpu=manifest.get('gpu'),
        timing=dict(started_at=status.get('started_at'),completed_at=status.get('completed_at'),elapsed_s=(end-start).total_seconds(),is_final=finished),
        completed_tasks=sum(r['completed'] for r in task_rows),observed_successes=sum(r['success'] is True for r in task_rows),
        final_successes=(effective_audit.get('successes') if accepted else None),final_success_task_ids=(effective_audit.get('success_task_ids') if accepted else None),
        stage=stage_counts(stages),mechanism=mechanism_counts(metrics,mode),
        compute_completed_episode_totals={k:sum_known(compute,k) for k in COMPUTE_KEYS},
        infrastructure_error_files=[str(p) for p in (folder/'output').glob('episode_*/error.txt')],
        tasks=task_rows,artifacts=artifacts,common_identity={k:identity(v) for k,v in common.items()},
        fresh_audit=fresh,audit_file_sha256=artifacts.get(str(folder/'audit.json'),{}).get('sha256'))
    return result,common

def aggregate(runs_root,suffix,now=None,revalidator=fresh_audit):
    now=now or datetime.now(timezone.utc);runs={};common={}
    for mode in MODES:
        try:runs[mode],common[mode]=inspect_run((Path(runs_root)/(mode+'-'+suffix)).resolve(),mode,now,revalidator)
        except Exception as exc:runs[mode]=dict(method=mode,state='evidence_error',accepted=False,error_type=type(exc).__name__,error=str(exc))
    shared={}
    if len(common)==3:
        shared={key:all(common[m][key]==common['eds'][key] for m in MODES) for key in common['eds']}
        shared['source_commit_present']=bool(common['eds']['commit'])
    else:shared['all_three_cohorts_readable']=False
    cohorts_valid=all(r.get('accepted') is True for r in runs.values()) and all(shared.values())
    eds_score=runs.get('eds',{}).get('final_successes')
    performance_pass=(eds_score>=3) if type(eds_score) is int else None
    integration_accepted=cohorts_valid and performance_pass is True
    state=('final_accepted' if integration_accepted else ('cohorts_valid_integration_threshold_not_met' if cohorts_valid else 'partial_or_not_accepted'))
    return dict(schema='steering_three_mode_aggregation_v1',created_at=now.isoformat(),
        state=state,all_cohorts_valid=cohorts_valid,integration_acceptance=integration_accepted,final_accepted=integration_accepted,
        performance_gate=dict(method='eds',reference_successes=3,denominator=10,observed_successes=eds_score,passed=performance_pass,
            scope='Integration performance threshold; does not change validity of scientifically unsuccessful episodes or completed cohorts.'),
        scope='Completed valid cohort scores remain visible. Integration acceptance additionally requires EDS at least3/10 after all shared-contract and fresh read-only audit gates pass.',
        shared_checks=shared,common_commit=common.get('eds',{}).get('commit'),
        intentional_config_exclusions=list(PATH_EXCLUSIONS+METHOD_EXCLUSIONS),runs=runs,
        comparison=dict(final_success_counts={m:r['final_successes'] for m,r in runs.items()} if cohorts_valid else None,
            validated_cohort_success_counts={m:r.get('final_successes') for m,r in runs.items()},
            denominator_per_mode=10,paired_task_ids=TASKS,seeds=SEEDS),
        limits=['No causal attribution from a single seed per task; provider and device variation are recorded.',
            'VLS and EDS have different actual compute budgets, reported separately; no equal-compute claim.',
            'Live JSONL reads are prefixes and may observe a trailing incomplete line.',
            'Method telemetry checks do not independently establish all descriptor geometry or executed tensor paths.',
            'Task contract detail timestamps are regenerated; fresh task outcome/check summaries are compared semantically, while cached detail file hashes remain independently checked. Method detail canonical hashes must exactly match the fresh reconstruction.',
            'No cross-chunk archive learning or recursive self-improvement is claimed.'])

def markdown(report):
    lines=['# Three-mode steering evaluation', '', 'Status: **'+report['state']+'**.', '',
        'Integration acceptance requires three finished, valid full v2 audits, identical shared source/assets/RNG/protocol, and EDS at least 3/10. Cohort validity and integration performance are separate gates.', '',
        '| Mode | State | Completed | Observed successes | Validated cohort score | GPU / EGL | Stage queries / errors | Guided chunks | Elapsed seconds |',
        '|---|---|---:|---:|---|---|---|---:|---:|']
    for mode,r in report['runs'].items():
        if 'completed_tasks' not in r:
            lines.append(f"| {mode} | {r['state']} | — | — | — | — | — | — | — |");continue
        score=f"{r['final_successes']}/10" if r.get('accepted') is True else 'Pending'
        lines.append(f"| {mode} | {r['state']} | {r['completed_tasks']}/10 | {r['observed_successes']} | {score} | {r['physical_gpu']} / {r['egl_device_id']} | {r['stage']['queries']} / {r['stage']['query_errors']} | {r['mechanism']['recorded_chunks']} | {r['timing']['elapsed_s']:.1f} |")
    lines+=['','All cohorts valid: **'+str(report['all_cohorts_valid'])+'**. Integration accepted: **'+str(report['integration_acceptance'])+'**.',
        'EDS integration threshold: at least 3/10; observed validated score: '+str(report['performance_gate']['observed_successes'])+'.',
        '','Common commit: `'+str(report.get('common_commit'))+'`.','',
        'Shared checks: '+', '.join(k+('=PASS' if v else '=FAIL') for k,v in report['shared_checks'].items())+'.','',
        'Per-task seeds, provisional outcomes, videos, timings, compute counters, mechanism counts, source and audit hashes are in the adjacent JSON report. Unknown counters remain unknown; observed subtotals are labelled.','',
        'Pending cohorts have no validated score. A completed valid cohort retains its score even if EDS falls below the integration threshold; that outcome is not relabeled invalid.','']
    return '\n'.join(lines)

def write_outputs(report,prefix,runs_root,replace=False):
    prefix=Path(prefix).resolve();root=Path(runs_root).resolve()
    if prefix.is_relative_to(root):raise ValueError('Outputs must be outside raw runs')
    paths=[prefix.with_suffix('.json'),prefix.with_suffix('.md')]
    if not replace and any(p.exists() for p in paths):raise FileExistsError('Choose a new external output prefix, or explicitly --replace')
    prefix.parent.mkdir(parents=True,exist_ok=True)
    paths[0].write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');paths[1].write_text(markdown(report))
    return paths

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs-root',type=Path,default=Path(__file__).resolve().parent.parent/'runs')
    parser.add_argument('--suffix',default='common-20261013')
    parser.add_argument('--output-prefix',type=Path,required=True)
    parser.add_argument('--replace',action='store_true')
    args=parser.parse_args();report=aggregate(args.runs_root,args.suffix)
    paths=write_outputs(report,args.output_prefix,args.runs_root,args.replace)
    print(json.dumps(dict(state=report['state'],all_cohorts_valid=report['all_cohorts_valid'],integration_acceptance=report['integration_acceptance'],final_accepted=report['final_accepted'],performance_gate=report['performance_gate'],shared_checks=report['shared_checks'],outputs=[str(p) for p in paths])))
    return 0 if report['final_accepted'] else 2
if __name__=='__main__':raise SystemExit(main())
