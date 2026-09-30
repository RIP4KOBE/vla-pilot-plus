"""Metadata-only cohort selection and dispatch exposure registration."""
import hashlib
import json
import os
from pathlib import Path
from scripts import qd_ed_n25_validation_contract as c
require=c.require
sha=c.sha
ref=c.ref
read=c.read
COHORT=c.COHORT
ARMS=c.ARMS
FIELDS=c.FIELDS
HISTORY_SHA='304c99c7f6df75a68c3278df0640c6a5bb744d04b2457d5991881e9ac4b2b573'

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
            if not line.strip():continue
            v=json.loads(line)
            rows.append({'pair':pair(v,'episode_seed'),'attempt_id':v.get('attempt_id'),
                         'cohort_id':v.get('cohort_id')})
        identities.append(rows)
    ledger=[]
    for line in blobs[2].splitlines():
        if not line.strip():continue
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
    require(not any(v['split']=='validation' and v['profile']=='N25' and v['attempt_id'] not in own for v in ledger),
            'N25 validation already reserved; one cohort only')
    require(not any(v['iteration']==COHORT for v in ledger) or allow_own,'N25 cohort already started')
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
                    'episode_key':f'n25v_{cohort}_b{b}_t{task:02d}_{arm.lower()}_20260930'})
    return result


def register_dispatch(root,event):
    """Journal-first exposure metadata; caller owns state lock, no outcome read."""
    if event.get('event')!='dispatched' or event.get('identity',{}).get('iteration')!=COHORT:return
    path=Path(root)/'data/exposure-registry.jsonl';i=event['identity']
    value={'schema':'n25-validation-dispatch-exposure-v1','cohort_id':COHORT,'attempt_id':event['attempt_id'],
        'task_id':i['task_id'],'episode_seed':i['env_seed'],'policy_seed':i['policy_seed'],
        'seed_block':event['n25_validation_seed_block'],'init_row_sha256':event['init_row_sha256'],
        'study_role':'validation','exposure_kind':'actual_dispatch','outcomes_read':False}
    with path.open('a') as stream:
        stream.write(json.dumps(value,sort_keys=True)+'\n');stream.flush();os.fsync(stream.fileno())
