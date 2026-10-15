#!/usr/bin/env python3
"""Read completed VLS tasks; only write independent checks, never raw cohorts."""
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
RUN = ROOT / '.worktrees/exp/steering-integration/runs/vls-common-20261013'
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
    if manifest.get('commit') != PIN or manifest.get('method') != 'vls':
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
from scripts.audit_steering import audit_vls_chunk, vls_reference_continuity
config=yaml.safe_load((RUN/'resolved-config.yaml').read_bytes())
EVALUATION=RUN/manifest['evaluation_directory']


def task_audit(episode, task, seed, computed, video, stages, metrics):
    source=source_guard(manifest)
    contract=audit_run(RUN,task=task,model=manifest['model'],effort=manifest['reasoning_effort'])
    write(OUT/f'task{task}-contract.json',contract)
    sk=lambda x:(x.get('episode_id'),x.get('task_id'),x.get('global_step'))
    mk=lambda x:(x.get('episode'),x.get('task_id'),x.get('global_step'))
    guided=[s for s in stages if s.get('guidance_after') is True]
    keys=[sk(s) for s in guided]; metric_keys=[mk(m) for m in metrics]
    chunk_reports=[]
    for metric in metrics:
        result=audit_vls_chunk(metric,config)
        identity=mk(metric)
        bound=(identity in keys and identity[:2]==(episode,task) and metric.get('episode_seed')==seed
            and metric.get('method_label')=='vls' and metric.get('job_id')==RUN.name
            and metric.get('suite')==config['backend']['libero']['suite_name'])
        chunk_reports.append(dict(identity=identity,stage_binding_valid=bound,**result))
    checks={
        'task_contract_valid':contract.get('task_contract_valid') is True,
        'task_evidence_complete':contract.get('task_evidence_complete') is True,
        'compute_identity':computed.get('episode_id')==episode and computed.get('task_id')==task and computed.get('episode_seed')==seed,
        'compute_completed':computed.get('outcome')=='completed',
        'terminal_video':video.is_file() and video.stat().st_size>0 and '_error' not in video.name,
        'no_episode_error':not (video.parent/'error.txt').exists(),
        'stage_seed_binding':bool(stages) and all(s.get('episode_seed')==seed for s in stages),
        'guided_chunk_complete_unique':bool(keys) and keys==metric_keys and len(keys)==len(set(keys))==len(set(metric_keys)),
        'compute_guided_count':computed.get('guided_chunks')==len(keys),
        'compute_unguided_count':computed.get('unguided_chunks')==sum(s.get('guidance_after') is False for s in stages),
        'chunk_mechanisms':bool(chunk_reports) and all(c['recorded_mechanism_valid'] and c['stage_binding_valid'] for c in chunk_reports),
        'stage_outer_reward_consumption_and_reference':vls_reference_continuity(stages,metrics),
    }
    counts={family:{key:sum(m[family][key] for m in metrics) for key in ('attempted','applied','zero','nonfinite','exception','unavailable')} for family in ('gradient','rbf')}
    counts['fkd']={key:sum(m['fkd']['diagnostics'][key] for m in metrics) for key in ('calls','score_opportunities','actual_resamples','ess_skips')}
    ess=[e['ess'] for m in metrics for e in m['fkd']['diagnostics']['events'] if e.get('ess') is not None]
    contact=[{k:s.get(k) for k in ('global_step','normalized_reward_diagnostic','contact_trigger','contact_phase','contact_until','guidance_before','guidance_after','target_distance_m','reward_reference_reset')} for s in stages if s.get('reward_used_for_contact_handoff') is True]
    progress=[m['outer_reward']['progress'] for m in metrics]
    report=dict(schema='vls_completed_task_live_audit_v1',audited_at=now(),task_id=task,episode=episode,seed=seed,
        valid=all(checks.values()),checks=checks,source=source,
        outcome='success' if '_success' in video.name else 'failure',outcome_scope='Recorded terminal video plus completed compute; cohort final validity remains pending',
        video=dict(path=str(video.relative_to(RUN)),bytes=video.stat().st_size,sha256=sha(video.read_bytes())),
        evidence_hashes=dict(compute_sha256=sha(canonical(computed)),stages_sha256=sha(canonical(stages)),metrics_sha256=sha(canonical(metrics)),contract_sha256=sha((OUT/f'task{task}-contract.json').read_bytes())),
        contract_summary=contract.get('summary'),guided_chunks=len(metrics),stage_boundaries=len(stages),counts=counts,
        ess_range=[min(ess),max(ess)] if ess else None,outer_progress_range=[min(progress),max(progress)] if progress else None,
        stage_progress=dict(fresh_diagnostic_boundaries=sum(s.get('guidance_before') is True and s.get('normalized_reward_diagnostic') is not None for s in stages),
            reference_resets=sum(s.get('reward_reference_reset') is True for s in stages),reward_handoff_events=contact),
        chunks=chunk_reports,
        limits=['Offline frozen-source checks of recorded evidence only; no model execution or simulator replay.',
                'Independent completed-task review complements but does not replace final full v2 cohort audit.'])
    write(OUT/f'task{task}-audit.json',report)
    notify(dict(event='task_audited',task_id=task,valid=report['valid'],outcome=report['outcome'],guided_chunks=len(metrics),counts=counts,
        contract_summary=contract.get('summary'),handoff_events=len(contact),failed_checks=[k for k,v in checks.items() if not v],report=str(OUT/f'task{task}-audit.json')))
    return report


def summary(reports,status):
    totals={family:{key:sum(r['counts'][family][key] for r in reports) for key in keys} for family,keys in
        [('gradient',('attempted','applied','zero','nonfinite','exception','unavailable')),('rbf',('attempted','applied','zero','nonfinite','exception','unavailable')),('fkd',('calls','score_opportunities','actual_resamples','ess_skips'))]}
    return dict(schema='vls_completed_task_live_audit_summary_v1',updated_at=now(),commit=PIN,run=str(RUN),worker_state=status.get('state'),
        audited_tasks=[r['task_id'] for r in reports],all_audited_valid=bool(reports) and all(r['valid'] for r in reports),
        complete_ten_task_review=len(reports)==10,cohort_final_acceptance=False,
        guided_chunks=sum(r['guided_chunks'] for r in reports),counts=totals,
        fresh_progress_consumed_boundaries=sum(r['stage_progress']['fresh_diagnostic_boundaries'] for r in reports),
        reference_resets=sum(r['stage_progress']['reference_resets'] for r in reports),
        reward_handoff_events=sum(len(r['stage_progress']['reward_handoff_events']) for r in reports),
        task_reports=[dict(task_id=r['task_id'],valid=r['valid'],outcome=r['outcome'],path=str(OUT/f"task{r['task_id']}-audit.json")) for r in reports])


def main():
    reports={read(p)['task_id']:read(p) for p in OUT.glob('task*-audit.json')}
    notify(dict(event='watch_started',pid=os.getpid(),commit=PIN,run=str(RUN),already_audited=sorted(reports),interval_seconds=30))
    while True:
        status=read(RUN/'status.json')
        compute=rows(EVALUATION/'episode_compute.jsonl')
        pending=[]
        for episode,(task,seed) in enumerate(zip(manifest['tasks'],manifest['seeds'])):
            if task in reports: continue
            records=[c for c in compute if c.get('episode_id')==episode and c.get('task_id')==task]
            if len(records)>1: raise ValueError(f'Duplicate compute record for task {task}')
            if len(records)!=1 or records[0].get('outcome')!='completed': continue
            videos=list((RUN/'output'/f'episode_{episode+1}').glob('*agentview.mp4'))
            if len(videos)>1: raise ValueError(f'Duplicate terminal video for task {task}')
            if not videos or videos[0].stat().st_size==0: continue
            pending.append((episode,task,seed,records[0],videos[0]))
        if pending:
            all_stages=rows(EVALUATION/'stage_events.jsonl');all_metrics=rows(EVALUATION/'vls_metrics.jsonl')
            for episode,task,seed,record,video in pending:
                stages=[s for s in all_stages if (s.get('episode_id'),s.get('task_id'))==(episode,task)]
                metrics=[m for m in all_metrics if (m.get('episode'),m.get('task_id'))==(episode,task)]
                reports[task]=task_audit(episode,task,seed,record,video,stages,metrics)
            write(OUT/'summary.json',summary([reports[k] for k in sorted(reports)],status))
        if status.get('state') in ('finished','exited','failed','error'):
            result=summary([reports[k] for k in sorted(reports)],status)
            result['final_source_check']=source_guard(manifest)
            write(OUT/'summary.json',result)
            notify(dict(event='watch_finished',worker_state=status.get('state'),audited_tasks=sorted(reports),all_audited_valid=result['all_audited_valid'],complete_ten_task_review=result['complete_ten_task_review'],counts=result['counts']))
            return
        time.sleep(30)

if __name__=='__main__':
    try: main()
    except Exception as exc:
        failure=dict(event='watch_error',at=now(),error_type=type(exc).__name__,error=str(exc))
        write(OUT/'watch-error.json',failure);notify(failure);raise
