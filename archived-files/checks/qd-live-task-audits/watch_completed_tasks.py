#!/usr/bin/env python3
"""Read completed QD tasks; only write independent checks, never raw cohorts."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[5]
RUN = ROOT / '.worktrees/exp/steering-integration/runs/eds_qd-common-20261013'
OUT = Path(__file__).resolve().parent
PIN = '33954ead452927fc3168efb610487a688f89169e'
sys.path.insert(0, str(ROOT))


def read(path): return json.loads(path.read_bytes())
def canonical(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
def sha(data): return hashlib.sha256(data).hexdigest()
def write(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)
def notify(value): print(json.dumps(value, allow_nan=False), flush=True)
def now(): return datetime.now(timezone.utc).isoformat()
def rows(path):
    if not path.exists(): return []
    data=path.read_bytes(); lines=data.splitlines(); result=[]
    for i, line in enumerate(lines):
        if not line.strip(): continue
        try: value=json.loads(line)
        except ValueError:
            if i==len(lines)-1 and not data.endswith(b'\n'): break
            raise ValueError(f'Malformed complete JSONL line: {path}:{i+1}')
        if not isinstance(value,dict): raise ValueError(f'Non-object JSONL: {path}:{i+1}')
        result.append(value)
    return result

def source_guard(manifest):
    if manifest.get('commit') != PIN or manifest.get('method') != 'eds_qd':
        raise ValueError('Frozen source/method identity changed')
    failures=[]
    for relative, expected in manifest['source_sha256'].items():
        for base in (ROOT, RUN/'source'):
            path=base/relative
            if not path.resolve().is_relative_to(base.resolve()):
                failures.append(str(path)); continue
            if not path.is_file() or sha(path.read_bytes()) != expected: failures.append(str(path))
    if failures: raise ValueError('Source hash changed: '+repr(failures))
    for relative,field in [('resolved-config.yaml','config_sha256'),('environment.json','environment_sha256'),('local-config.yaml','local_config_sha256')]:
        if sha((RUN/relative).read_bytes()) != manifest[field]: raise ValueError('Run identity changed: '+relative)
    fixture=ROOT/'tests/fixtures/steering_rng/fixture-manifest.json'
    env=read(RUN/'environment.json')
    if sha(fixture.read_bytes())!=env['rng']['sha256']: raise ValueError('Current RNG fixture manifest changed')
    return dict(commit=PIN, source_files_verified=len(manifest['source_sha256']), source_manifest_sha256=sha(canonical(manifest['source_sha256'])))

manifest=read(RUN/'manifest.json')
source_guard(manifest)
import yaml
from scripts.audit_steering_contract import audit_run
from scripts.audit_qd_mechanism import audit_chunk
config=yaml.safe_load((RUN/'resolved-config.yaml').read_bytes())
EVALUATION=RUN/manifest['evaluation_directory']



def task_audit(episode, task, seed, computed, video, stages, metrics):
    from collections import Counter
    source=source_guard(manifest)
    contract=audit_run(RUN,task=task,model=manifest['model'],effort=manifest['reasoning_effort'])
    write(OUT/f'task{task}-contract.json',contract)
    sk=lambda x:(x.get('episode_id'),x.get('task_id'),x.get('global_step'))
    mk=lambda x:(x.get('episode'),x.get('task_id'),x.get('global_step'))
    guided=[s for s in stages if s.get('guidance_after') is True]
    keys=[sk(s) for s in guided];metric_keys=[mk(m) for m in metrics]
    reports=[]
    for number,metric in enumerate(metrics,1):
        identity=mk(metric)
        bound=(identity in keys and identity[:2]==(episode,task)
            and ('episode_seed' not in metric or metric['episode_seed']==seed)
            and metric.get('method_label')=='eds_qd' and metric.get('job_id')==RUN.name
            and metric.get('suite')==config['backend']['libero']['suite_name'])
        try:
            result=audit_chunk(metric,config['main']['eds_config'],expected_mode='eds_qd')
            expected_steps=[dict(iter_idx=i,n_trunc_steps=n,step_count=count,
                step_flags=[True]*count+[False]*(n-count),step_indices=list(range(count)),
                final_step_rbf_applied=count==n,fallback_used=False)
                for i,(n,count) in enumerate(zip([3,2,2,2,2,1,1,1,1,1],[2,2,2,2,2,1,1,1,1,1]))]
            sampler=(metric.get('initial_sampling_mode')=='rbf_diverse_denoise'
                and metric.get('initial_diversity_steps')==4 and metric.get('initial_diversity_fallback_used') is False
                and metric.get('rollout_diversity_mode')=='rbf_diverse' and metric.get('rollout_diversity_fallback_used') is False
                and metric.get('rollout_diversity_iters_applied')==10 and metric.get('rollout_rbf_steps_by_iter')==expected_steps)
            result['checks']['fixed_rbf_sampler_execution']='pass' if sampler else 'fail'
            result['recorded_mechanism_valid']=result.get('recorded_mechanism_valid') is True and sampler
            canonical(result)
        except Exception as exc:
            result={'recorded_mechanism_valid':False,'checks':{'evidence_structure':'fail'},'error_type':type(exc).__name__,'error':str(exc)}
        reports.append(dict(row_number=number,identity=identity,stage_binding_valid=bound,**result))
    checks={
        'task_contract_valid':contract.get('task_contract_valid') is True,
        'task_evidence_complete':contract.get('task_evidence_complete') is True,
        'compute_identity':computed.get('episode_id')==episode and computed.get('task_id')==task and computed.get('episode_seed')==seed,
        'compute_completed':computed.get('outcome')=='completed',
        'terminal_video':video.is_file() and video.stat().st_size>0 and '_error' not in video.name,
        'no_episode_error':not (video.parent/'error.txt').exists(),
        'stage_task_seed_binding':bool(stages) and all((s.get('episode_id'),s.get('task_id'),s.get('episode_seed'))==(episode,task,seed) for s in stages),
        'guided_chunk_complete_unique':bool(keys) and keys==metric_keys and len(keys)==len(set(keys))==len(set(metric_keys)),
        'compute_guided_count':computed.get('guided_chunks')==len(keys),
        'compute_unguided_count':computed.get('unguided_chunks')==sum(s.get('guidance_after') is False for s in stages),
        'chunk_mechanisms':bool(reports) and all(c['recorded_mechanism_valid'] and c['stage_binding_valid'] for c in reports),
    }
    counts=dict(guided_chunks=len(metrics),score_calls=sum(m.get('score_call_count',0) for m in metrics),
        candidate_evaluations=sum(m.get('search_evaluation_count',0) for m in metrics),
        qd_evaluations=sum(m.get('qd_evaluation_count',0) for m in metrics),
        active_archive_chunks=sum(m.get('qd_archive_active_for_chunk') is True for m in metrics),
        parent_sources=dict(sum((Counter(m.get('parent_count_by_source',{})) for m in metrics),Counter())),
        final_selection_sources=dict(Counter(m.get('selected_parent_source','missing') for m in metrics)))
    final_cells=[m['qd_occupied_cells_by_iter'][-1] for m in metrics if m.get('qd_occupied_cells_by_iter')]
    final_coverage=[m['qd_coverage_ratio_by_iter'][-1] for m in metrics if m.get('qd_coverage_ratio_by_iter')]
    visits=[sum(m['qd_cumulative_cell_visits_by_iter'][-1]) for m in metrics if m.get('qd_cumulative_cell_visits_by_iter')]
    rewards=[m['qd_selected_reward'] for m in metrics if isinstance(m.get('qd_selected_reward'),(int,float))]
    archive=dict(final_occupied_cells_histogram=dict(Counter(final_cells)),
        final_coverage_min=min(final_coverage) if final_coverage else None,
        final_coverage_mean=sum(final_coverage)/len(final_coverage) if final_coverage else None,
        final_coverage_max=max(final_coverage) if final_coverage else None,
        final_candidate_visit_totals_histogram=dict(Counter(visits)),
        total_insertions=sum(m.get('qd_initial_accounting',{}).get('insertions',0)+sum(m.get('qd_archive_insertions_by_iter',[])) for m in metrics),
        total_replacements=sum(sum(m.get('qd_archive_replacements_by_iter',[])) for m in metrics),
        total_rejections=sum(m.get('qd_initial_accounting',{}).get('rejections',0)+sum(m.get('qd_archive_rejections_by_iter',[])) for m in metrics),
        overflow_candidates=sum(m.get('qd_initial_descriptor_overflow_count',0)+sum(m.get('qd_descriptor_overflow_count_by_iter',[])) for m in metrics),
        selected_reward_min=min(rewards) if rewards else None,selected_reward_max=max(rewards) if rewards else None)
    scalar_compute={k:v for k,v in computed.items() if type(v) in (int,float,bool) or v is None}
    final_source=source_guard(manifest)
    report=dict(schema='qd_completed_task_live_audit_v1',audited_at=now(),task_id=task,episode=episode,seed=seed,
        valid=all(checks.values()),checks=checks,source=source,source_after_audit=final_source,
        outcome='success' if '_success' in video.name else 'failure',outcome_scope='Recorded terminal video plus completed compute; cohort final validity remains pending',
        video=dict(path=str(video.relative_to(RUN)),bytes=video.stat().st_size,sha256=sha(video.read_bytes())),
        evidence_hashes=dict(compute_sha256=sha(canonical(computed)),stages_sha256=sha(canonical(stages)),metrics_sha256=sha(canonical(metrics)),contract_sha256=sha((OUT/f'task{task}-contract.json').read_bytes())),
        contract_summary=contract.get('summary'),guided_chunks=len(metrics),stage_boundaries=len(stages),
        stage_queries=sum(s.get('query_status') in ('ok','error') for s in stages),stage_errors=sum(s.get('query_status')=='error' for s in stages),
        counts=counts,archive=archive,compute=scalar_compute,chunks=reports,
        limits=['Offline frozen-source checks of recorded evidence only; no model or simulator execution.',
          'Independent task review complements but does not replace the final full v2 cohort audit.',
          'EDS/QD metric seed binding is indirect through task/episode and matching Stage/compute/manifest identity when the metric omits episode_seed.',
          'Descriptor geometry and actual executed parent/selection tensors are not independently replayed.',
          'Archives are fresh per chunk; no cross-chunk or recursive self-improvement claim.',
          'Task failure, low archive coverage, ties and finite descriptor overflow remain legal scientific outcomes.'])
    write(OUT/f'task{task}-audit.json',report)
    notify(dict(event='task_audited',task_id=task,valid=report['valid'],outcome=report['outcome'],counts=counts,archive=archive,
        contract_summary=contract.get('summary'),failed_checks=[k for k,v in checks.items() if not v],
        failed_chunks=[dict(identity=c['identity'],failed_checks={k:v for k,v in c.get('checks',{}).items() if v not in ('pass',True)}) for c in reports if not c['recorded_mechanism_valid']],
        report=str(OUT/f'task{task}-audit.json')))
    return report


def summary(reports,status):
    from collections import Counter
    numeric=('guided_chunks','score_calls','candidate_evaluations','qd_evaluations','active_archive_chunks')
    counts={k:sum(r['counts'][k] for r in reports) for k in numeric}
    for k in ('parent_sources','final_selection_sources'):
        counts[k]=dict(sum((Counter(r['counts'][k]) for r in reports),Counter()))
    occupied=dict(sum((Counter(r['archive']['final_occupied_cells_histogram']) for r in reports),Counter()))
    visits=dict(sum((Counter(r['archive']['final_candidate_visit_totals_histogram']) for r in reports),Counter()))
    return dict(schema='qd_completed_task_live_audit_summary_v1',updated_at=now(),commit=PIN,run=str(RUN),worker_state=status.get('state'),
        audited_tasks=[r['task_id'] for r in reports],all_audited_valid=bool(reports) and all(r['valid'] for r in reports),
        complete_ten_task_review=len(reports)==10,cohort_final_acceptance=False,
        observed_success_task_ids=[r['task_id'] for r in reports if r['outcome']=='success'],
        counts=counts,final_occupied_cells_histogram=occupied,final_candidate_visit_totals_histogram=visits,
        stage_queries=sum(r['stage_queries'] for r in reports),stage_errors=sum(r['stage_errors'] for r in reports),
        model_forward_calls=sum(r['compute'].get('model_forward_calls',0) for r in reports),
        model_batch_rows=sum(r['compute'].get('model_batch_rows',0) for r in reports),
        task_reports=[dict(task_id=r['task_id'],valid=r['valid'],outcome=r['outcome'],path=str(OUT/f"task{r['task_id']}-audit.json"),sha256=sha((OUT/f"task{r['task_id']}-audit.json").read_bytes())) for r in reports])


def main():
    reports={read(p)['task_id']:read(p) for p in OUT.glob('task*-audit.json')}
    notify(dict(event='watch_started',pid=os.getpid(),commit=PIN,run=str(RUN),already_audited=sorted(reports),interval_seconds=30))
    while True:
        status=read(RUN/'status.json');compute=rows(EVALUATION/'episode_compute.jsonl');pending=[]
        for episode,(task,seed) in enumerate(zip(manifest['tasks'],manifest['seeds'])):
            if task in reports:continue
            records=[c for c in compute if c.get('episode_id')==episode or c.get('task_id')==task]
            if len(records)>1:raise ValueError(f'Duplicate/conflicting compute record for task {task}')
            if len(records)!=1 or records[0].get('outcome')!='completed':continue
            videos=list((RUN/'output'/f'episode_{episode+1}').glob('*agentview.mp4'))
            if len(videos)>1:raise ValueError(f'Duplicate terminal video for task {task}')
            if not videos or videos[0].stat().st_size==0:continue
            pending.append((episode,task,seed,records[0],videos[0]))
        if pending:
            all_stages=rows(EVALUATION/'stage_events.jsonl');all_metrics=rows(EVALUATION/'eds_metrics.jsonl')
            for episode,task,seed,record,video in pending:
                stages=[s for s in all_stages if s.get('episode_id')==episode or s.get('task_id')==task]
                metrics=[m for m in all_metrics if m.get('episode')==episode or m.get('task_id')==task]
                reports[task]=task_audit(episode,task,seed,record,video,stages,metrics)
            write(OUT/'summary.json',summary([reports[k] for k in sorted(reports)],status))
        if status.get('state') in ('finished','exited','failed','error'):
            result=summary([reports[k] for k in sorted(reports)],status);result['final_source_check']=source_guard(manifest)
            write(OUT/'summary.json',result)
            notify(dict(event='watch_finished',worker_state=status.get('state'),audited_tasks=sorted(reports),all_audited_valid=result['all_audited_valid'],complete_ten_task_review=result['complete_ten_task_review'],counts=result['counts']))
            return
        time.sleep(30)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        failure=dict(event='watch_error',at=now(),error_type=type(exc).__name__,error=str(exc))
        write(OUT/'watch-error.json',failure);notify(failure);raise
