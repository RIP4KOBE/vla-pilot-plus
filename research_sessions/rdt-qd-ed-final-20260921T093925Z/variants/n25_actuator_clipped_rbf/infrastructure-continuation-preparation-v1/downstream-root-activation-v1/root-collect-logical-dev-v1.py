#!/usr/bin/env python3
"""Root collector, run only after independent terminal review under immutable 6f.
Writes Dev/resource metadata projections and a disabled inventory for root review.
Never follows tensor/image/raw Stage/private outcome references.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

HERE=Path(__file__).resolve()
N25=HERE.parents[2]
R=N25.parents[1]
W=R/'study_worktree'
C=N25/'infrastructure-continuation-v1'
D=N25/'infrastructure-continuation-preparation-v1'
sys.path[:0]=[str(W/'scripts'),str(W)]
from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n25_cont_evidence as e
from scripts import qd_ed_n25_cont_contract as c
from scripts import qd_ed_n25_cont_terminal as terminal
from scripts import qd_ed_n25_backend as backend

HISTORICAL='6f796358aa84d53e9c8a04859f7d19352c9db7fe'
DISPOSITIONS={'ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION','REJECT','REJECT_NUMERIC_FUTILITY'}
DENIED={'events.jsonl','stage_events.jsonl','stage_responses.jsonl','attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl'}
DEST=C/'logical-dev-preparation-v1'
LIMIT=16*1024*1024

def bounded(path):
    p=Path(path)
    e.require(p.is_absolute() and p.is_file() and not p.is_symlink(),'missing/linked metadata')
    size=p.stat().st_size
    e.require(0<=size<=LIMIT,'metadata size cap')
    with p.open('rb') as f: b=f.read(size+1)
    e.require(len(b)==size,'metadata changed during read')
    return b

def fresh_ref(path):
    p=Path(path).resolve()
    e.require(p.suffix in {'.json','.jsonl','.txt'} and p.name not in DENIED,'excluded metadata role')
    e.require(not any(k in p.parts for k in ('decision_evidence','images','videos')),'payload excluded')
    return {'path':str(p),'sha256':hashlib.sha256(bounded(p)).hexdigest()}

def get(ref):
    b=bounded(ref['path'])
    e.require(hashlib.sha256(b).hexdigest()==ref['sha256'],'metadata digest changed')
    return json.loads(b)

def write(path,data):
    with path.open('x') as f: json.dump(data,f,indent=2,allow_nan=False); f.write('\n')

def project(ledger,predicate):
    # Normal private journal identity/cost access only. Never emits foreign events.
    # Hash the exact stream used for the projection; no unrelated payload files.
    h=hashlib.sha256(); selected=[]; size=0
    with ledger.open('rb') as f:
        for line in f:
            size+=len(line)
            e.require(len(line)<=LIMIT and size<=128*1024*1024,'private journal bound')
            h.update(line)
            if line.strip():
                event=json.loads(line)
                if predicate(event): selected.append(event)
    return selected,{'path':str(ledger.resolve()),'sha256':h.hexdigest()}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--after-reviewed-terminal',action='store_true',required=True)
    p.parse_args()
    e.require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','CPU-only collector')
    with runner.locked(C/'execution/supervisor.lock',nonblocking=True):
      with runner.locked(W/'data/qd-ed-runner.lock',nonblocking=True):
        paths={k:DEST/n for k,n in {
          'journal_projection':'current-dev-journal-projection-v1.json',
          'resource_projection':'current-resource-projection-v1.json',
          'input':'metadata-input-draft-v1.json',
          'roles':'root-metadata-roles-v1.json'}.items()}
        e.require(not any(p.exists() for p in paths.values()),'immutable collector output exists')
        refs={k:fresh_ref(v) for k,v in {
          'source':D/'source-manifest-v1.json','seal':c.SEAL,'seal_review':c.SEAL_REVIEW,
          'source_bridge':c.BRIDGE,'source_review':c.FINAL_REVIEW,'authority':c.AUTHORITY,
          'release':C/'execution-release-v1.json','plan':c.PLAN,
          'status':C/'execution/supervisor-status-v1.json','result':C/'result-v1.json',
          'root_review':C/'root-terminal-review-v1.json',
          'controller':C/'execution/controller-process-v1.json'}.items()}
        source=get(refs['source']); seal=get(refs['seal']); result=get(refs['result'])
        review=get(refs['root_review']); controller=get(refs['controller'])
        e.require(source['commit']==HISTORICAL and review['source']==source
          and review['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION'
          and review['cohort_disposition']==result['decision'] in DISPOSITIONS
          and review['result']==refs['result'] and review['controller']==refs['controller'],
          'valid independently reviewed closure required')
        for q in source['files']:
            e.require(e.sha(W/q['path'])==q['sha256'],'collect before downstream source integration')
        e.process_cleanup([controller['process']])
        e.verify_absences(seal['failed_audits_absent'])
        e.require(review['cleanup']['no_owned_processes'] is True,'terminal cleanup unaccepted')
        refs['old_source']=next(q for q in seal['metadata_files'] if q['sha256']==e.FROZEN['source'])
        proof=get(seal['historical_backend_proof']); proofplan=get(proof['plan'])
        rid=proofplan['resource_id']; kind=backend.KIND
        events,ledger_ref=project(W/'data/attempt-ledger.jsonl',
          lambda x:x.get('identity',{}).get('iteration') in {e.OLD,c.COHORT})
        original=[x for x in events if x['identity']['iteration']==e.OLD]
        continuation=[x for x in events if x['identity']['iteration']==c.COHORT]
        e.require(original==get(seal['old_ledger']) and continuation==get(result['ledger_snapshot']),
          'later/changed matching journal')
        resources,resource_ledger_ref=project(W/'data/gpu-healthcheck-ledger.jsonl',
          lambda x:x.get('resource_id')==rid or x.get('kind')==kind)
        e.require(len(resources)==3 and [x['event'] for x in resources]==['reserved','dispatched','completed']
          and resources[-1]==get(proof['terminal']),'original resource settlement changed')
        base={'root_terminal_review':refs['root_review'],'collector':e.ref(HERE),
          'collected_at':datetime.now(timezone.utc).isoformat(),'all_matching_events_included':True,
          'protected_events_included':False}
        jp={**base,'schema':'n25-current-dev-journal-projection-v1','source_ledger':ledger_ref,
          'original_events':original,'continuation_events':continuation,
          'original_event_count':len(original),'continuation_event_count':len(continuation)}
        rp={**base,'schema':'n25-current-resource-projection-v1','source_ledger':resource_ledger_ref,
          'resource_id':rid,'resource_kind':kind,'events':resources,'event_count':len(resources)}
        records={}; roles={}
        def add(q,role):
            key=str(Path(q['path']).resolve())
            e.require(Path(key).name not in DENIED,'excluded metadata inventory entry')
            e.require(key not in records or e.same_ref(records[key],q),'conflicting metadata reference')
            records[key]=q; roles.setdefault(key,[]).append(role)
        for q in seal['metadata_files']: add(q,'previously sealed original metadata')
        for key,q in refs.items(): add(q,'explicit '+key)
        for q in terminal.metadata_inventory(result,continuation): add(q,'independent terminal typed metadata')
        for key in ('plan','report','process','terminal'): add(proof[key],'original settled resource '+key)
        add(seal['historical_backend_proof'],'original settled resource proof')
        add(get(refs['authority'])['existing_budget_authority'],'original adopted budget authority')
        # Verify the closed pre-projection universe before writing anything.
        reader=e.Reader(list(records.values()))
        for q in records.values(): reader.read_bytes(q)
        DEST.mkdir(parents=True,exist_ok=True)
        for key,data in (('journal_projection',jp),('resource_projection',rp)):
            write(paths[key],data);refs[key]=fresh_ref(paths[key]);add(refs[key],'new root current projection')
        data={'schema':'n25-logical-dev-evidence-input-v1','root_authorized':False,
          'owning_root':str(W.resolve()),'files':list(records.values()),'references':refs}
        write(paths['input'],data)
        write(paths['roles'],{'schema':'n25-root-metadata-role-review-input-v1',
          'input':fresh_ref(paths['input']),'files':roles,'preprojection_verified_bytes':reader.bytes,
          'tensor_reads':0,'raw_stage_reads':0,'protected_payload_reads':0,
          'admission_or_execution_authorized':False})
        print(json.dumps({'draft':fresh_ref(paths['input']),'roles':fresh_ref(paths['roles']),
          'metadata_files':len(records),'root_authorized':False,
          'continuation_disposition':result['decision'],'accepted_cells':result['audited_cells']}))

if __name__=='__main__':main()

