"""Read-only PI05 cohort audit; standard LIBERO results never become RDT OOD results."""
from pathlib import Path
import argparse
import json
import re
import sys
import yaml
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.steering_runtime import digest, atomic_json
from scripts.pi05_runtime import load_config
from scripts.audit_steering_contract import audit_run
from scripts.audit_steering import runtime_compatibility_checks, provider_manifest_matches_config


def read(path):
    return json.loads(Path(path).read_text())


def metric_valid(row):
    if row.get('schema') != 'pi05_vls_chunk_v1' or row.get('finite') is not True:
        return False
    if row.get('checkpoint_load',{}).get('strict') is not True or row.get('executed_candidate_index') != 0:
        return False
    if row.get('compute_delta',{}).get('model_forward_calls') != 10 or row.get('execution_horizon') != 10:
        return False
    if row.get('guidance'):
        fkd = row.get('fkd') or {}
        scored = [e for e in fkd.get('events',[]) if e.get('scored')]
        return (row.get('reward_gradient_applied',0)>0 and row.get('rbf_gradient_applied',0)>0
                and row.get('reward_gradient_unavailable')==0
                and row.get('sample_batch_size')==20
                and [e.get('timestep') for e in scored]==[2,7,9]
                and sorted(scored[-1].get('terminal_sort_indices') or [])==list(range(20)))
    return row.get('fkd') is None


def audit(folder):
    folder = Path(folder).resolve(); checks = {}; tasks=[]; errors={}
    def check(name, condition):
        try: checks[name] = bool(condition() if callable(condition) else condition)
        except Exception as exc: checks[name]=False;errors[name]=str(exc)
    try:
        manifest=read(folder/'manifest.json'); status=read(folder/'status.json')
        cfg=yaml.safe_load((folder/'resolved-config.yaml').read_text())
        local=yaml.safe_load((folder/'local-config.yaml').read_text())
        env=read(folder/'environment.json')
        check('pi05_schema',manifest.get('schema')=='pi05_vls_cohort_v1' and manifest.get('policy')=='pi05')
        for name,key in [('resolved-config.yaml','config_sha256'),('local-config.yaml','local_config_sha256'),('environment.json','environment_sha256')]:
            check(name,lambda name=name,key=key:digest(folder/name)==manifest[key])
        check('source_snapshot_intact',lambda:bool(manifest['source_sha256']) and all(digest(folder/'source'/p)==h for p,h in manifest['source_sha256'].items()))
        expected=load_config(local,cfg['hydra']['run']['dir'],manifest['tasks'],source_root=folder/'source')
        expected['perception']['vlm_agent']['query_template_dir']=str(Path(manifest['code_root'])/'vlm_query/target_distance')
        check('fixed_protocol',cfg==expected and manifest['seeds']==cfg['main']['episode_seed_schedule'])
        check('worker_complete',status.get('state')=='finished' and status.get('exit_code')==0)
        check('source_unchanged_during_run',status.get('source_unchanged') is True)
        check('online_provider',provider_manifest_matches_config(manifest,cfg) and manifest['reasoning_effort']=='ultra')
        check('gpu_binding',env['device_mapping']['gpu']==local['gpu']==manifest['physical_gpu'] and env['device_mapping']['egl_device_id']==local['egl_device_id']==manifest['egl_device_id'])
        checks.update(runtime_compatibility_checks(folder,manifest,env))
        expected_assets=read(folder/'source/scripts/public_model_sources.json')['huggingface']
        expected_rows=[dict(root=k,**r) for k in ('pi05_checkpoint','pi05_tokenizer') for r in expected_assets[k]['files']]
        expected_rows += [r for r in read(folder/'source/scripts/steering_model_assets_manifest.json')['files'] if r['root']=='torch_home']
        check('exact_asset_receipt',env['model_assets']['valid'] is True and env['model_assets']['files']==expected_rows)
        evaluation=folder/'output/evaluation'
        streams={name:[json.loads(line) for line in (evaluation/(name+'.jsonl')).read_text().splitlines() if line.strip()]
                 for name in ('episode_metadata','episode_compute','pi05_metrics','stage_events')}
        identity=lambda row:(row.get('episode_id'),row.get('task_id'),row.get('episode_seed'))
        identities=[(i,t,s) for i,(t,s) in enumerate(zip(manifest['tasks'],manifest['seeds']))]
        for name in ('episode_metadata','episode_compute'):
            check(name+'_identity',[identity(r) for r in streams[name]]==identities)
        compute=streams['episode_compute'];metrics=streams['pi05_metrics']
        check('episodes_completed',all(r.get('outcome')=='completed' for r in compute))
        check('mechanism_chunks',bool(metrics) and all(metric_valid(r) for r in metrics))
        check('all_metric_tasks_known',all(r.get('task_id') in manifest['tasks'] for r in metrics))
        check('no_episode_errors',not list((folder/'output').glob('episode_*/error.txt')))
        for index,task in enumerate(manifest['tasks'],1):
            episode=folder/'output'/f'episode_{index}'
            videos=list(episode.glob('*agentview.mp4'))
            video_ok=len(videos)==1 and '_error' not in videos[0].name
            task_metrics=[r for r in metrics if r.get('task_id')==task]
            task_ok=bool(task_metrics) and any(r.get('guidance') for r in task_metrics)
            check(f'task{task}_chunk_sequence',[r['chunk_id'] for r in task_metrics]==list(range(len(task_metrics))))
            row_compute=next((r for r in compute if r['task_id']==task),{})
            for key in ('model_forward_calls','model_batch_rows','guided_chunks','unguided_chunks','reward_gradient_calls','rbf_gradient_calls'):
                check(f'task{task}_compute_{key}',sum(r['compute_delta'].get(key,0) for r in task_metrics)==row_compute.get(key))
            contract=audit_run(folder,task=task,model=manifest['model'],effort=manifest['reasoning_effort'])
            valid=video_ok and task_ok and contract['task_contract_valid']
            tasks.append(dict(task_id=task,seed=manifest['seeds'][index-1],valid=valid,
                success=video_ok and '_success' in videos[0].name,
                videos=[str(v.relative_to(folder)) for v in videos],chunks=len(task_metrics),
                contract_summary=contract['summary'],
                failed_contract_checks=[k for k,v in contract['checks'].items() if v['status']!='pass']))
        check('all_task_evidence_valid',len(tasks)==len(manifest['tasks']) and all(r['valid'] for r in tasks))
        count=re.search(r'Success count:\s*(\d+)/(\d+)',(folder/'output/results.txt').read_text())
        check('environment_success_count',bool(count) and (int(count[1]),int(count[2]))==(sum(r['success'] for r in tasks),len(tasks)))
    except Exception as exc:
        checks['evidence_readable']=False;errors['evidence_readable']=f'{type(exc).__name__}: {exc}'
    return dict(schema='pi05_vls_audit_v1',valid=bool(checks) and all(checks.values()),
                benchmark='libero_object',checks=checks,errors=errors,tasks=tasks,
                successes=sum(r['success'] for r in tasks),completed=sum(r['valid'] for r in tasks),
                limitations=['Runtime mechanism counters and checkpoint loading are attestations, not independent replay.',
                             'One episode per task is a smoke benchmark, not the upstream multi-trial score.'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir');parser.add_argument('--report')
    args=parser.parse_args();result=audit(args.run_dir)
    if args.report:
        if Path(args.report).exists():raise FileExistsError(args.report)
        atomic_json(args.report,result)
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0 if result['valid'] else 2

if __name__=='__main__':raise SystemExit(main())
