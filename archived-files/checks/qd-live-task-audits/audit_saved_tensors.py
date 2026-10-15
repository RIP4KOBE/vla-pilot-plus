#!/usr/bin/env python3
"""CPU-only supplementary checks of saved traces from independently audited tasks."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('qd_frozen_watch_guard', HERE / 'watch_completed_tasks.py')
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)
import torch
from scripts.audit_qd_mechanism import audit_chunk


def tensor_fields(stage):
    return {k: {'shape': list(v.shape), 'dtype': str(v.dtype), 'device': str(v.device)}
            for k, v in stage.items() if torch.is_tensor(v)}


def main():
    out = HERE / 'tensor-evidence'
    out.mkdir(exist_ok=True)
    source = watch.source_guard(watch.manifest)
    completed = {r['task_id']: (p, r) for p in HERE.glob('task*-audit.json')
                 if (r := watch.read(p)).get('valid') is True}
    metrics = watch.rows(watch.EVALUATION / 'eds_metrics.jsonl')
    stages = watch.rows(watch.EVALUATION / 'stage_events.jsonl')
    reports = []
    for trace in sorted((watch.EVALUATION / 'qualitative').rglob('mechanism_trace.pt')):
        # Directory identity is checked again against the actual trace and metric.
        episode = int(trace.parents[2].name.removeprefix('episode_'))
        step = int(trace.parents[1].name.removeprefix('chunk_'))
        if not 0 <= episode < len(watch.manifest['tasks']):
            raise ValueError('Unexpected trace episode: ' + str(trace))
        task = watch.manifest['tasks'][episode]
        if task not in completed:
            continue
        seed = watch.manifest['seeds'][episode]
        destination = out / f'task{task}-step{step}.json'
        before = watch.sha(trace.read_bytes())
        selected = [m for m in metrics if (m.get('episode'), m.get('task_id'), m.get('global_step')) == (episode, task, step)]
        stage = [s for s in stages if (s.get('episode_id'), s.get('task_id'), s.get('global_step')) == (episode, task, step)]
        if len(selected) != 1 or len(stage) != 1:
            raise ValueError(f'Nonunique trace/Stage/metric binding: task {task}, step {step}')
        metric, event = selected[0], stage[0]
        inputs = dict(trace_sha256=before, metric_sha256=watch.sha(watch.canonical(metric)),
                      stage_sha256=watch.sha(watch.canonical(event)),
                      completed_task_report_sha256=watch.sha(completed[task][0].read_bytes()))
        if destination.exists():
            previous = watch.read(destination)
            if previous.get('inputs') != inputs:
                raise ValueError('Previously audited trace evidence changed: ' + str(destination))
            reports.append((destination, previous))
            continue
        payload = torch.load(trace, weights_only=True, map_location='cpu')
        meta = payload.get('metadata', {})
        checks = dict(
            cuda_hidden=os.environ.get('CUDA_VISIBLE_DEVICES') == '' and not torch.cuda.is_initialized(),
            manifest_task_seed=(task, seed) == (completed[task][1]['task_id'], completed[task][1]['seed']),
            trace_directory_identity=all(type(meta.get(k)) is int and meta[k] == v for k, v in
                                         [('episode', episode), ('task_id', task), ('global_step', step)]),
            stage_binding=event.get('guidance_after') is True and event.get('episode_seed') == seed,
            metric_binding=metric.get('method_label') == 'eds_qd' and metric.get('job_id') == watch.RUN.name
                           and metric.get('suite') == watch.config['backend']['libero']['suite_name']
                           and ('episode_seed' not in metric or metric['episode_seed'] == seed),
            completed_task_audit=completed[task][1]['valid'] is True,
        )
        result = audit_chunk(metric, watch.config['main']['eds_config'], trace_payload=payload, expected_mode='eds_qd')
        checks['trace_and_archive_reconstruction'] = result['recorded_mechanism_valid'] is True
        checks['trace_bytes_unchanged'] = watch.sha(trace.read_bytes()) == before
        source_after = watch.source_guard(watch.manifest)
        report = dict(schema='steering_qd_saved_tensor_evidence_v1', generated_at=datetime.now(timezone.utc).isoformat(),
                      task_id=task, episode=episode, seed=seed, global_step=step, valid=all(checks.values()),
                      checks=checks, inputs=inputs, trace_path=str(trace.relative_to(watch.RUN)), trace_bytes=trace.stat().st_size,
                      source=source, source_after=source_after,
                      tensor_stage_inventory=[dict(stage=s.get('stage'), iter_idx=s.get('iter_idx'), tensors=tensor_fields(s))
                                              for s in payload.get('stages', [])],
                      audit=result, cohort_acceptance=None,
                      limitations=[
                          'Only these saved chunk prefixes have tensor evidence; this is not all-chunk tensor verification.',
                          'Candidate batches: -1 means the initial population; 0..9 mean candidates after each rollout.',
                          'Verified parent iterations refer to saved resampled tensors matching independently reconstructed ordered archive parents.',
                          'Missing resampled tensors for other iterations cannot establish their actual parent tensor path.',
                          'Rewards/descriptors remain recorded inputs; projection geometry, reward execution, final returned and executed tensors are not independently replayed.',
                          'Saved snapshots do not independently prove all downstream model tensor consumption.',
                          'Per-task success remains a separate recorded scientific outcome; tensor checks do not change it.',
                      ])
        watch.write(destination, report)
        reports.append((destination, report))
        print(json.dumps(dict(event='tensor_trace_audited', task_id=task, global_step=step, valid=report['valid'],
                              parent_iterations=result['parent_tensor_verified_iterations'],
                              candidate_batches=result['candidate_tensor_verified_batches'],
                              failed_checks={k: v for k, v in result['checks'].items() if v != 'pass'})), flush=True)
    summary = dict(schema='steering_qd_saved_tensor_summary_v1', generated_at=datetime.now(timezone.utc).isoformat(),
                   source=watch.source_guard(watch.manifest), completed_tasks_considered=sorted(completed),
                   valid=bool(reports) and all(r['valid'] for _, r in reports), cohort_acceptance=None,
                   reports=[dict(task_id=r['task_id'], global_step=r['global_step'], valid=r['valid'],
                                 parent_tensor_verified_iterations=r['audit']['parent_tensor_verified_iterations'],
                                 candidate_tensor_verified_batches=r['audit']['candidate_tensor_verified_batches'],
                                 full_parent_tensor_path_verified=r['audit']['full_parent_tensor_path_verified'],
                                 descriptor_geometry_verified=r['audit']['descriptor_geometry_verified'],
                                 executed_selected_tensor_verified=r['audit']['executed_selected_tensor_verified'],
                                 path=str(p), sha256=watch.sha(p.read_bytes())) for p, r in reports])
    watch.write(out / 'summary.json', summary)
    print(json.dumps(dict(event='tensor_summary', valid=summary['valid'], reports=len(reports),
                          completed_tasks_considered=summary['completed_tasks_considered'], path=str(out / 'summary.json'))), flush=True)
    return 0 if summary['valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
