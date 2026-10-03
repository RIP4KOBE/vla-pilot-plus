"""Finite N30 metadata closure; no historical validator/tensor replay."""
import hashlib,json,math
from pathlib import Path
from scripts import qd_ed_n23_worker as w
BASE='7c0d80d734fa8300173e56d9a8de03415bc55fe2'
OLD_SOURCE='4ce2b95757c1c0d662696ba19d6a9a14d2e59b49'
OLD='N30_EXECUTED_PROGRESS_CONTINUATION_DEV_20261003'
COHORT='N30_INITIAL_OBSERVATION_REPAIR_DEV_20261003'
FAILED='rdt-qd-ed-final-20260921T093925Z__n30_dev_t00_n30_20261003__5bf10b19849f'
DOC='docs/experiments/n30/r1'
CHANGED={'scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py'}
PLAN_SHA='dacc57c2434cb36720216566dde69b4832753f1108d8f8380033a7de54054c31'
REVIEW_SHA='7d64075cbe49bb44d1f644912c87595f58236bb41db31d37e17d80d579429e17'
REPAIR_SHA='6e5dc3c0a83236d463ed6d920d5f724f676094547c70189e7e4c224d10ba75fa'
OLD_SECONDS=1090.1433259700425
ARMS=('C0','Q0','N30')
MAX_FILE=8*1024*1024
MAX_TOTAL=64*1024*1024


def finite(v):return type(v) in (int,float) and math.isfinite(v) and v>=0

def group(events):
    result={}
    for e in events:result.setdefault(e['attempt_id'],[]).append(e)
    return list(result.values())

class Reader:
    def __init__(self):self.bytes=0;self.refs={}
    def read(self,ref,*,text=False):
        w.require(set(ref)=={'path','sha256'},'r1 metadata ref schema')
        p=Path(ref['path']);w.require(p.is_absolute() and not p.is_symlink() and p.is_file() and p.stat().st_size<=MAX_FILE,'r1 metadata path/size')
        with p.open('rb') as f:data=f.read(MAX_FILE+1)
        self.bytes+=len(data);w.require(len(data)<=MAX_FILE and self.bytes<=MAX_TOTAL and hashlib.sha256(data).hexdigest()==ref['sha256'],'r1 metadata byte/hash bound')
        self.refs[str(p)]=ref['sha256'];return data.decode() if text else json.loads(data)


def history(root):
    root=Path(root);release=json.loads((root/DOC/'root-cpu-integration-release-v1.json').read_text());reader=Reader()
    w.require(release['closed_original']['sha256']==REVIEW_SHA and release['repair_review']['sha256']==REPAIR_SHA,'r1 exact reviews')
    review=reader.read(release['closed_original']);repair=reader.read(release['repair_review'])
    w.require(review['schema']=='n30-root-terminal-review-v1' and review['decision']=='INVALID_OR_INTERRUPTED'
        and review['source_commit']==OLD_SOURCE and review['source_files_rehashed']==439 and review['dispatched']==3 and review['audited_cells']==2
        and review['controller_original_process_exited'] is True and review['monitor_original_process_exited'] is True
        and review['retry_count']==0 and review['gpu_preparation_seconds']==0 and review['episode_gpu_seconds_observed']==OLD_SECONDS
        and review['original_ledger_modified'] is False and review['new_gpu_release'] is False,'r1 named original closure')
    w.require(repair['schema']=='n30-root-initial-observation-repair-review-v1' and repair['disposition']=='ACCEPT_CPU_REPAIR_ONLY'
        and repair['base_commit']==OLD_SOURCE and repair['commit']==BASE and repair['algorithm_changed'] is False
        and repair['old_complete_method_ast_independently_bound'] is True,'r1 accepted exact repair')
    source=reader.read(review['source']);plan=reader.read(review['plan']);result=reader.read(review['result']);events=reader.read(review['terminal_ledger'])
    w.require(source==json.loads((root/DOC/'original-source-v1.json').read_text()) and source['commit']==OLD_SOURCE
        and len(source['files'])==439 and source['sha256']==w.canonical_sha(source['files'])
        and review['plan']['sha256']==PLAN_SHA and plan['frozen'] is True and plan['source_commit']==OLD_SOURCE and plan['code_files']==source['files'], 'r1 old source/plan')
    rows=plan['episodes'];w.require(len(rows)==12 and [(x['task_id'],x['profile']) for x in rows]==[(t,a) for t in range(4) for a in ARMS]
        and len({x['episode_key'] for x in rows})==12 and all(x['iteration']==OLD and x['split']==x['seed_block']=='dev'
        and x['timeout_seconds']==1800 and x['budget_bucket']==('baseline' if x['profile']=='C0' else 'development') and not x.get('retry_of') for x in rows),'r1 original matrix')
    gg=group(events);w.require(len(gg)==3 and len(events)==9 and events==sum(gg,[]) and len({g[0]['attempt_id'] for g in gg})==3,'r1 original groups')
    for row,g in zip(rows,gg):
        final=g[-1];identity={k:row[k] for k in ('split','iteration','profile','task_id','env_seed','policy_seed','init_index')}
        w.require([e['event'] for e in g]==['reserved','dispatched','valid'] and all(e['episode_key']==row['episode_key'] and e['identity']==identity and not e.get('retry_of') for e in g)
            and final['source_commit']==OLD_SOURCE and final['plan_sha256']==PLAN_SHA and finite(final.get('gpu_process_wall_seconds')),'r1 original identity/cost')
    w.require(sum(g[-1]['gpu_process_wall_seconds'] for g in gg)==OLD_SECONDS and result['decision']=='INVALID_OR_INTERRUPTED'
        and result['source_commit']==OLD_SOURCE and result['audited_cells']==2 and result['dispatched']==3
        and result['accepted_cells']==review['accepted_cells'],'r1 original result/cost differs')
    exited=review['worker_original_processes_exited']
    w.require(len(exited)==3 and [x['attempt_id'] for x in exited]==[g[-1]['attempt_id'] for g in gg] and all(x['original_process_exited'] is True for x in exited),'r1 cleanup attestation')
    w.require(len(review['accepted_cells'])==2,'r1 exact inherited count')
    imports=[]
    for i,cell in enumerate(review['accepted_cells']):
        row=rows[i];final=gg[i][-1]
        w.require(cell['episode_key']==row['episode_key'] and cell['profile']==ARMS[i] and cell['task_id']==0 and cell['success'] is False
            and cell['attempt_id']==final['attempt_id'] and final['outcome_valid'] is True and final['success'] is False and final['required_cost_telemetry_complete'] is True,'r1 exact two inherited controls')
        artifact={k:reader.read(cell[k]) for k in ('attempt_result','worker_context','worker_receipt','audit')}
        ctx,rec,audit=artifact['worker_context'],artifact['worker_receipt'],artifact['audit']
        w.require(artifact['attempt_result']==final and ctx['source']==source and ctx['plan']==review['plan'] and ctx['attempt_id']==cell['attempt_id']
            and ctx['episode_key']==row['episode_key'] and ctx['profile']==row['profile'] and ctx['runtime']=={'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']}
            and rec['context']==cell['worker_context'] and rec['source']==source and rec['plan']==review['plan'] and rec['runtime']==ctx['runtime']
            and rec['attempt_id']==cell['attempt_id'] and rec['episode_key']==row['episode_key'] and rec['profile']==row['profile']
            and rec['accepted'] is True and rec['main_exit_code']==0 and rec['process_unchanged'] is True and rec['audit_report']==cell['audit']
            and rec['evidence']['sha256']==w.canonical_sha(rec['evidence']['files']) and rec['audit_backend']['kind']=='cpu'
            and audit['accepted'] is True and audit['evidence_complete'] is True and audit['n30_executed_progress_audit']['profile']==row['profile']
            and final['n23_worker_receipt']==cell['worker_receipt'],'r1 inherited receipt/context source lineage')
        imports.append({'cell':{**cell,'source_commit':OLD_SOURCE,'inherited':True},'terminal':final,'native':rec['n30_native_counts'],'auxiliary':rec['n30_auxiliary']})
    w.require(len(imports)==2,'r1 prefix count')
    bad=review['invalid_attempts'];final=gg[2][-1]
    w.require(len(bad)==1 and bad[0]['attempt_id']==final['attempt_id']==FAILED and bad[0]['episode_key']==rows[2]['episode_key']
        and bad[0]['outcome_valid'] is False and final['outcome_valid'] is False and final['failure_class']=='task_failure'
        and bad[0]['root_classification']=='ENGINEERING_INITIAL_OBSERVATION_UNBOUNDLOCAL'
        and all(bad[0][k]==0 for k in ('model_forward_calls','guided_chunks','unguided_chunks','provider_logical_call_attempts'))
        and reader.read(bad[0]['attempt_result'])==final,'r1 sole named invalid signature')
    error=reader.read(bad[0]['error'],text=True)
    w.require("UnboundLocalError: cannot access local variable 'obs' where it is not associated with a value" in error and '_run_episode' in error,'r1 exact error differs')
    budget=reader.read(plan['n30_cohort']['budget_reuse'])
    return {'review':review,'repair_review':repair,'source':source,'plan':plan,'events':events,'imports':imports,'old_seconds':OLD_SECONDS,
        'budget':budget,'refs':[{'path':p,'sha256':s} for p,s in sorted(reader.refs.items())],
        'historical_trust':'Root verified old source/processes/receipts/raw integrity under original HEAD; this reader rehashes finite metadata only, never follows evidence.files tensor refs.'}


def current_subset(h,events):
    w.require([e for e in events if e.get('identity',{}).get('iteration')==OLD]==h['events'],'r1 later/mutated original reservation')


def source_paths(root):
    root=Path(root);base=json.loads((root/DOC/'base-source-v1.json').read_text());paths={x['path'] for x in base['files']}
    for pattern in ('scripts/qd_ed_n30_r1_*.py','tests/test_n30_r1*.py','tests/n30_r1*.py',DOC+'/*'):
        paths.update(str(p.relative_to(root)) for p in root.glob(pattern) if p.is_file())
    return paths


def reverse_source(root,source):
    root=Path(root);base=json.loads((root/DOC/'base-source-v1.json').read_text());patch=json.loads((root/DOC/'reverse-source-v1.json').read_text())
    index={x['path']:x['sha256'] for x in source['files']}
    w.require(base['commit']==BASE and patch['base_commit']==BASE and set(index)==source_paths(root) and len(index)==len(source['files']) and set(patch['files'])==CHANGED,'r1 source closure')
    for f in base['files']:
        data=(root/f['path']).read_bytes();w.require(hashlib.sha256(data).hexdigest()==index[f['path']],'r1 source bytes')
        if f['path'] in CHANGED:
            e=patch['files'][f['path']];w.require(e['old_sha256']==f['sha256'] and e['new_sha256']==index[f['path']],'r1 reversal hashes')
            lines=data.decode().splitlines(keepends=True)
            for h in reversed(e['hunks']):
                w.require(lines[h['start']:h['end']]==h['new'],'r1 reverse hunk');lines[h['start']:h['end']]=h['old']
            data=''.join(lines).encode()
        w.require(hashlib.sha256(data).hexdigest()==f['sha256'],'r1 unauthorized prior source change')
    return base


def build(source,runtime,root):
    w.verify_source(root,source);base=reverse_source(root,source);h=history(root)
    w.require(runtime=={'path':h['plan']['runtime_manifest_path'],'sha256':h['plan']['runtime_manifest_sha256']},'r1 runtime unchanged')
    return {'schema':'n30-r1-source-history-bridge-v1','source':source,'repair_base_source':base,'original_source':h['source'],'runtime':runtime,
        'metadata_refs':h['refs'],'imports':h['imports'],'old_gpu_seconds':h['old_seconds'],'original_disposition':'INVALID_OR_INTERRUPTED',
        'historical_trust':h['historical_trust'],'new_standalone_proof':False,'gpu_release':False}
