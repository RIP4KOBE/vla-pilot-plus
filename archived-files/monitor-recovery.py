"""Read-only run monitor; no launch, resume or retry decisions."""
import datetime,hashlib,json,pathlib,time
base=pathlib.Path(__file__).resolve().parent
freeze=json.loads((base/'checks/freeze-transport-recovery.json').read_text())
repo=base.parents[2]

def rows(path):
    result=[]
    if path.exists():
        for line in path.read_text().splitlines():
            try: x=json.loads(line)
            except ValueError: continue
            if isinstance(x,dict): result.append(x)
    return result

def read(path):
    try: return json.loads(path.read_text())
    except (OSError,ValueError): return {}

def snapshot():
    value={'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'runs':{}}
    value['source_unchanged']=all(hashlib.sha256((repo/p).read_bytes()).hexdigest()==h for p,h in freeze['source_sha256'].items())
    for method,gpu in [('eds',0),('vls',1),('eds_qd',4)]:
        folder=base/'runs'/(method+'-ultra-recovery-full10-01');status=read(folder/'status.json');progress=read(folder/'progress.json');audit=read(folder/'audit.json')
        evaluation=folder/'output/evaluation';completed=rows(evaluation/'episode_compute.jsonl');events=rows(evaluation/'stage_events.jsonl');meta=rows(evaluation/'episode_metadata.jsonl')
        row=dict(gpu=gpu,state=status.get('state','not_started'),pid=status.get('pid'),**progress)
        row['completed']=sum(x.get('outcome')=='completed' for x in completed);row['infra_errors']=sum(x.get('outcome')!='completed' for x in completed)
        row['provisional_successes']=sum('_success' in x.name for x in (folder/'output').glob('episode_*/*agentview.mp4'))
        if events:row.update(task_id=events[-1].get('task_id'),step=events[-1].get('global_step'))
        elif meta:row['task_id']=meta[-1].get('task_id')
        row['stage_queries']=sum(x.get('query_status') in ('ok','error') for x in events)
        row['audited_valid']=audit.get('valid');row['audited_successes']=audit.get('successes');value['runs'][method]=row
    return value

if __name__=='__main__':
    while True:
        value=snapshot();target=base/'live-progress-recovery.json';temp=base/'live-progress-recovery.tmp';temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(target)
        print(json.dumps(value),flush=True)
        if all(r['state'] in ('finished','preflight_failed','launcher_failed','interrupted') and (r['audited_valid'] is not None or r['state']!='finished') for r in value['runs'].values()):break
        time.sleep(30)
