import json, time, sys
from pathlib import Path
C = Path(__file__).resolve().parent
W = C.parents[2] / 'study_worktree'
COHORT = 'N27_HYDRA_CONTINUATION_V1_20261001'
def read(path, cap=16*1024*1024):
    path=Path(path)
    if not path.exists(): return None
    assert path.stat().st_size <= cap
    with path.open('rb') as stream: data=stream.read(cap+1)
    assert len(data)<=cap
    return json.loads(data)
def alive(record):
    if not record: return None
    try:
        text=(Path('/proc')/str(record['pid'])/'stat').read_text()
        fields=text[text.rfind(')')+2:].split()
        return fields[0]!='Z' and fields[19]==str(record['proc_start_ticks']) and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==record['boot_id']
    except FileNotFoundError: return False
status=read(C/'execution/supervisor-status-v1.json')
controller=read(C/'execution/controller-process-v1.json')
result=read(C/'result-v1.json')
events=[]
ledger=W/'data/attempt-ledger.jsonl'
assert ledger.stat().st_size < 32*1024*1024
with ledger.open() as stream:
    for line in stream:
        if not line.endswith('\n'): break
        event=json.loads(line)
        if event.get('identity',{}).get('iteration')==COHORT: events.append(event)
finals=[e for e in events if e['event'] in ('valid','aborted','invalid')]
dispatched=[e for e in events if e['event']=='dispatched']
settled={e['attempt_id'] for e in finals}
active=[e for e in dispatched if e['attempt_id'] not in settled]
current=None
if active:
    e=active[-1]
    process=read(Path(e['output_dir'])/'process.json')
    metric=Path(e['output_dir'])/'eds_eval/eds_metrics.jsonl'
    current={'profile':e['identity']['profile'],'task_id':e['identity']['task_id'],'attempt_id':e['attempt_id'],
             'seconds_since_dispatch':round(time.time()-e['time_unix'],1),'pid':(process or {}).get('pid'),
             'alive':alive(process),'metrics_bytes':metric.stat().st_size if metric.exists() else 0}
    stage_path=Path(e['output_dir'])/'eds_eval/stage_events.jsonl'
    if stage_path.is_file():
        assert stage_path.stat().st_size<16*1024*1024
        stages=[]
        with stage_path.open() as stream:
            for line in stream:
                if not line.endswith('\n'): break
                stages.append(json.loads(line))
        queried=[x for x in stages if x.get('codex_logical_call_attempts',0)]
        current.update(last_stage_recorded_step=max((x.get('global_step',0) for x in stages),default=None),
            stage_logical_calls=sum(x.get('codex_logical_call_attempts',0) for x in stages),
            stage_failed_calls=sum(x.get('codex_failed_calls',0) for x in stages),
            queried_routes_codex_chatgpt=all(x.get('transport',{}).get('backend')=='codex_cli' and x.get('transport',{}).get('auth_mode')=='chatgpt' for x in queried))
summary={'time_unix':time.time(),'controller_alive':alive(controller['process']) if controller else None,
    'status':status.get('status') if status else 'launch_validation','dispatched':len(dispatched),
    'accepted':len(status.get('completed_keys',[])) if status else 0,'current':current,
    'valid_outcomes':[{'profile':e['identity']['profile'],'task_id':e['identity']['task_id'],'success':e.get('success'),
                       'outcome_valid':e.get('outcome_valid'),'stage_calls':e.get('provider_logical_call_attempts'),
                       'stage_failed':e.get('provider_failed_calls'),'stage_backend':e.get('stage_backend')}
                      for e in finals],
    'failure':status.get('failure') if status else None,'terminal_decision':result.get('decision') if result else None}
if '--compact' in sys.argv:
    summary['closed_stage_calls']=sum(e.get('provider_logical_call_attempts',0) or 0 for e in finals)
    summary['closed_stage_failed']=sum(e.get('provider_failed_calls',0) or 0 for e in finals)
    summary['closed_counts']={arm:{'n':sum(e['identity']['profile']==arm for e in finals),
        'success':sum(e['identity']['profile']==arm and e.get('success') is True for e in finals)}
        for arm in ('C0','Q0','N26','N27')}
    summary['last_terminal']=summary.pop('valid_outcomes')[-1:] or None
    if current:
        current.pop('attempt_id',None)
        current.pop('metrics_bytes',None)
print(json.dumps(summary))
