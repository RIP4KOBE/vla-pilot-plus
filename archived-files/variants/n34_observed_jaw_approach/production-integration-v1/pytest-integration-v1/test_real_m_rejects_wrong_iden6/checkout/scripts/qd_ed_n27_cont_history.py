"""Bounded root-attested old metadata; never replay old controllers/raw evidence."""
import hashlib
import json
import math
from pathlib import Path
from scripts import qd_ed_n23_worker as w
BASE='095cfeecd6af55477d2529441c307ab712e8a8da'
OLD='N27_FEASIBLE_RAY_SCREEN_20261001'
COHORT='N27_HYDRA_CONTINUATION_V1_20261001'
FAILED='rdt-qd-ed-final-20260921T093925Z__n27_screen_t00_n27_20261001__1af7d45d9a10'
PLAN_SHA='8632a2f39f0cde0c198f358c1b1700907707d3e0474a75df6b9296cf18f7441f'
REVIEW_SHA='01dc887dc20d6050a498b15c575b881a3ad8471041c466818cad1ecb4aa8eaac'
CLASSIFICATION_SHA='276985ca84b8031060d329485097e2fb33ffaee5ea379abbedd9c05e97523ad1'
ARMS=('C0','Q0','N26','N27')
UNKNOWN=['original_invalid_required_cost_telemetry','original_invalid_provider_usage','original_invalid_native_outcome']
MAX_FILE=16*1024*1024
def ref(path):
    p=Path(path).resolve()
    w.require(p.is_file() and p.stat().st_size<=MAX_FILE,'metadata reference size/path')
    with p.open('rb') as stream:data=stream.read(MAX_FILE+1)
    w.require(len(data)<=MAX_FILE,'metadata reference grew beyond cap')
    return {'path':str(p),'sha256':hashlib.sha256(data).hexdigest()}

def read(reference):
    w.require(set(reference)=={'path','sha256'},'metadata ref schema')
    p=Path(reference['path'])
    w.require(p.is_absolute() and not p.is_symlink() and p.is_file() and p.stat().st_size<=MAX_FILE,'metadata path/size')
    with p.open('rb') as f:data=f.read(MAX_FILE+1)
    w.require(len(data)<=MAX_FILE and hashlib.sha256(data).hexdigest()==reference['sha256'],'metadata hash/size')
    return json.loads(data)

def finite(v):return type(v) in (int,float) and math.isfinite(v) and v>=0

def groups(events):
    result={}
    for event in events:result.setdefault(event['attempt_id'],[]).append(event)
    return result

def verify(seal):
    """Pure schema/identity checks. Root seal review attests receipt/raw/proof integrity."""
    w.require(seal.get('schema')=='n27-hydra-history-seal-v1' and seal.get('original_disposition')=='INVALID_OR_INTERRUPTED'
        and seal.get('original_source',{}).get('commit')==BASE and len(seal['original_source']['files'])==345
        and seal.get('original_plan',{}).get('sha256')==PLAN_SHA and seal.get('root_terminal_review',{}).get('sha256')==REVIEW_SHA
        and seal.get('startup_classification',{}).get('sha256')==CLASSIFICATION_SHA
        and seal.get('historical_unknowns')==UNKNOWN,'named historical seal differs')
    source=seal['original_source'];w.require(source['sha256']==w.canonical_sha(source['files'])
        and len({x['path'] for x in source['files']})==345,'old source digest')
    plan=seal['original_plan_content'];rows=plan['episodes']
    w.require(w.canonical_sha(plan)==seal['original_plan_content_sha256'] and plan['source_commit']==BASE
        and plan['code_files']==source['files'] and plan['frozen'] is True
        and len(rows)==16 and [(x['task_id'],x['profile']) for x in rows]==[(t,a) for t in range(4) for a in ARMS]
        and len({x['episode_key'] for x in rows})==16,'original screen/source matrix')
    for row in rows:w.require(row['iteration']==OLD and row['split']==row['seed_block']=='dev' and row['timeout_seconds']==1800
        and row['budget_bucket']==('baseline' if row['profile']=='C0' else 'development') and not row.get('retry_of'),'old row changed')
    w.require(seal['runtime']=={'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']},'runtime lineage')
    ev=seal['old_events'];gg=list(groups(ev).values())
    w.require(len(gg)==4 and len(ev)==12 and [g[0]['episode_key'] for g in gg]==[x['episode_key'] for x in rows[:4]],'old exact four attempts')
    for i,g in enumerate(gg):
        final=g[-1];row=rows[i]
        w.require([x['event'] for x in g]==['reserved','dispatched','valid'] and final['outcome_valid'] is (i<3)
            and final['source_commit']==BASE and final['plan_sha256']==PLAN_SHA and final['identity']['iteration']==OLD
            and all(x['attempt_id']==final['attempt_id'] and x['episode_key']==row['episode_key'] and x.get('retry_of') is None for x in g)
            and all(final['identity'][k]==row[k] for k in ('split','profile','task_id','env_seed','policy_seed','init_index'))
            and finite(final.get('gpu_process_wall_seconds')),'old attempt identity/terminal/cost')
        if i<3:w.require(final.get('required_cost_telemetry_complete') is True and final.get('success') is False,'three valid failed controls')
    w.require(gg[3][-1]['attempt_id']==FAILED and gg[3][-1]['gpu_process_wall_seconds']==7.231457023997791
        and gg[3][-1].get('required_cost_telemetry_complete') is not True,'named pre-main invalid retained')
    prefix=seal['accepted_prefix'];w.require(len(prefix)==3,'exact historical accepted prefix')
    for i,item in enumerate(prefix):
        cell=item['cell'];final=gg[i][-1]
        w.require(item['logical_index']==i and cell['episode_key']==rows[i]['episode_key'] and cell['task_id']==0
            and cell['profile']==ARMS[i] and cell['attempt_id']==final['attempt_id'] and cell['success'] is False
            and all(set(cell[k])=={'path','sha256'} for k in ('audit','worker_context','worker_receipt','attempt_result'))
            and isinstance(item['native'],dict) and isinstance(item['auxiliary'],dict),'historical cell binding')
    attempts=seal['all_old_attempts'];w.require(len(attempts)==4 and all(x['terminal']==g[-1] and x['attempt_id']==g[-1]['attempt_id']
        and x['episode_key']==g[-1]['episode_key'] and x['profile']==rows[i]['profile'] for i,(x,g) in enumerate(zip(attempts,gg))),'all original costs unchanged')
    health=seal['old_resource_events'];hg={}
    for event in health:hg.setdefault(event['resource_id'],[]).append(event)
    hg=list(hg.values())
    w.require(len(hg)==1 and [x['event'] for x in hg[0]]==['reserved','dispatched','completed'] and hg[0][-1].get('kind')=='n27_tensor_arithmetic_v1'
        and finite(hg[0][-1].get('gpu_process_wall_seconds')),'one settled historical proof resource')
    seconds=sum(g[-1]['gpu_process_wall_seconds'] for g in gg)+hg[0][-1]['gpu_process_wall_seconds']
    w.require(seal['old_gpu_seconds']==seconds and seconds<9.25*3600 and seal.get('cleanup_complete') is True
        and seal.get('no_active_owned_worker') is True,'old full costs/cleanup seal')
    for k in ('original_result','historical_backend_proof','original_source_review','original_authority','budget_authority'):
        w.require(set(seal[k])=={'path','sha256'},'historical ref missing: '+k)
    return seal

def current_subset(seal,events,resources):
    verify(seal)
    old=[x for x in events if x.get('identity',{}).get('iteration')==OLD]
    ids={x['resource_id'] for x in seal['old_resource_events']}
    resource=[x for x in resources if x.get('kind')=='n27_tensor_arithmetic_v1' or x.get('resource_id') in ids]
    w.require(old==seal['old_events'] and resource==seal['old_resource_events'],'historical subset drift/later old reservation')
    # Unrelated legitimate append-only ledger events are deliberately irrelevant here.
