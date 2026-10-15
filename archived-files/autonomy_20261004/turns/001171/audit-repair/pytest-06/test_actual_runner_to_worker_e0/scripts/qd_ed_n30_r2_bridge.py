"""R2 finite metadata lineage: two imported controls, two preserved invalids."""
import hashlib,json
from pathlib import Path
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n30_r1_bridge as original
BASE='debda23a0e8eda86a3bb4f398e9596edf05b37e5'
R1_SOURCE='b2775fa2008a8a88e374c43a5753f8862485af1f'
OLD_SOURCE=original.OLD_SOURCE
OLD=original.OLD
R1=original.COHORT
COHORT='N30_TERMINAL_BOOLEAN_REPAIR_DEV_20261003'
ORIGINAL_FAILED=original.FAILED
FAILED='rdt-qd-ed-final-20260921T093925Z__n30_r1_dev_t00_n30_20261003__2138c682c5a7'
DOC='docs/experiments/n30/r2'
CHANGED=original.CHANGED
PLAN_SHA=original.PLAN_SHA
REVIEW_SHA=original.REVIEW_SHA
R1_REVIEW_SHA='89377494b0fcd9030735c8ed27e2168bfa1204f8637328bb27ff6449f6f4cda4'
R1_PLAN_SHA='a70fa5d90433962f665e9a5b5a8758d6901408e914212b1ed12baeb1f9d8f5a9'
REPAIR_SHA='ed8d17d91231f516f699c076c21172fe95c3b508513f4646a1ecb70f0e282805'
R1_SECONDS=355.2775675270241
OLD_SECONDS=original.OLD_SECONDS+R1_SECONDS
ARMS=original.ARMS
MAX_FILE=8*1024*1024
MAX_TOTAL=64*1024*1024
finite=original.finite
group=original.group

class Reader:
    def __init__(self,prior_refs=()):
        self.refs={v['path']:v['sha256'] for v in prior_refs}
        self.bytes=sum(Path(p).stat().st_size for p in self.refs)
        w.require(self.bytes<=MAX_TOTAL,'r2 prior metadata cap')
    def read(self,ref):
        w.require(set(ref)=={'path','sha256'},'r2 metadata ref schema')
        p=Path(ref['path'])
        w.require(p.is_absolute() and not p.is_symlink() and p.is_file(),'r2 metadata path')
        size=p.stat().st_size
        w.require(size<=MAX_FILE and self.bytes+size<=MAX_TOTAL,'r2 metadata pre-read cap')
        with p.open('rb') as f:data=f.read(min(MAX_FILE,MAX_TOTAL-self.bytes)+1)
        self.bytes+=len(data)
        w.require(len(data)==size and self.bytes<=MAX_TOTAL and hashlib.sha256(data).hexdigest()==ref['sha256'],'r2 metadata hash/size')
        self.refs[str(p)]=ref['sha256'];return json.loads(data)


def history(root):
    root=Path(root)
    # Reuse only this finite metadata parser, not r1 source/admission/native validators.
    h=original.history(root);reader=Reader(h['refs'])
    release=json.loads((root/DOC/'root-cpu-integration-release-v1.json').read_text())
    w.require(release['base_source_commit']==BASE and release['closed_r1_execution_review']['sha256']==R1_REVIEW_SHA
        and release['accepted_repair_review']['sha256']==REPAIR_SHA,'r2 exact CPU repair/closure binding')
    review=reader.read(release['closed_r1_execution_review']);repair=reader.read(release['accepted_repair_review'])
    w.require(review['schema']=='n30-r1-root-terminal-review-v1' and review['decision']=='INVALID_OR_INTERRUPTED'
        and review['root_classification']=='NATIVE_AUDIT_TERMINAL_FEEDBACK_BINDING_FAILURE' and review['scientific_outcome']=='Unknown'
        and review['source_commit']==R1_SOURCE and review['source_files_rehashed']==457
        and review['new_dispatched']==1 and review['combined_dispatched']==4 and review['audited_cells']==2
        and all(review[k] is True for k in ('controller_original_process_exited','monitor_original_process_exited','worker_original_process_exited'))
        and review['new_episode_gpu_seconds']==R1_SECONDS and review['combined_episode_gpu_seconds']==OLD_SECONDS
        and review['gpu_preparation_seconds']==0 and review['original_ledger_modified'] is False
        and review['original_closure']=={'path':release_path(h),'sha256':original.REVIEW_SHA},'r2 named r1 invalid closure')
    w.require(repair['schema']=='n30-terminal-feedback-root-cpu-repair-review-v1' and repair['disposition']=='ACCEPT_CPU_REPAIR_ONLY'
        and repair['source_commit']==BASE and repair['base_commit']==R1_SOURCE and repair['source_files_rehashed']==463
        and repair['modified_base_files']==['scripts/qd_ed_n30_native.py'] and repair['unchanged_base_files']==456
        and repair['whole_file_reverse_independently_verified'] is True and repair['original_receipt_stays_invalid'] is True
        and repair['closed_gpu_execution']==release['closed_r1_execution_review'],'r2 strict repair review')
    repaired_source=reader.read(repair['source'])
    w.require(repaired_source==json.loads((root/DOC/'base-source-v1.json').read_text()) and repaired_source['commit']==BASE
        and len(repaired_source['files'])==463 and repaired_source['sha256']==w.canonical_sha(repaired_source['files']),'r2 repaired source snapshot')
    source=reader.read(review['source']);plan=reader.read(review['plan']);result=reader.read(review['result']);events=reader.read(review['terminal_ledger'])
    w.require(source==json.loads((root/DOC/'r1-source-v1.json').read_text()) and source['commit']==R1_SOURCE and len(source['files'])==457
        and source['sha256']==w.canonical_sha(source['files']) and review['plan']['sha256']==R1_PLAN_SHA
        and plan['source_commit']==R1_SOURCE and plan['code_files']==source['files'] and plan['frozen'] is True
        and plan['runtime_manifest_path']==h['plan']['runtime_manifest_path'] and plan['runtime_manifest_sha256']==h['plan']['runtime_manifest_sha256'], 'r2 historical r1 source/plan/runtime')
    rows=[]
    for i,oldrow in enumerate(h['plan']['episodes'][2:]):
        row=dict(oldrow);row.update(iteration=R1,episode_key=oldrow['episode_key'].replace('n30_dev_','n30_r1_dev_'),original_episode_key=oldrow['episode_key'])
        if i==0:row.update(budget_bucket='recovery',retry_of=ORIGINAL_FAILED)
        rows.append(row)
    w.require(plan['episodes']==rows and events[:len(h['events'])]==h['events'] and len(events)==len(h['events'])+3,'r2 exact r1 suffix/prefix')
    gg=group(events);g=events[-3:];row=rows[0];final=g[-1]
    identity={k:row[k] for k in ('split','iteration','profile','task_id','env_seed','policy_seed','init_index')}
    w.require(len(gg)==4 and events==sum(gg,[]) and [e['event'] for e in g]==['reserved','dispatched','valid']
        and all(e['attempt_id']==FAILED and e['identity']==identity and e['episode_key']==row['episode_key'] and e['budget_bucket']=='recovery'
            and e.get('retry_of')==ORIGINAL_FAILED and e['source_commit']==R1_SOURCE and e['plan_sha256']==R1_PLAN_SHA for e in g)
        and final['outcome_valid'] is False and final['failure_class']=='task_failure' and final['gpu_process_wall_seconds']==R1_SECONDS,'r2 exact failed group/cost')
    cells=[x['cell'] for x in h['imports']]
    w.require(review['accepted_cells']==cells and result['accepted_cells']==cells and result['schema']=='n30-r1-combined-result-v1'
        and result['decision']=='INVALID_OR_INTERRUPTED' and result['dev_gate_promoted'] is False and result['source_commit']==R1_SOURCE
        and result['new_dispatched']==1 and result['all_dispatched']==4 and result['audited_cells']==2
        and result['original_invalid_attempt']==ORIGINAL_FAILED and result['plan']==review['plan'] and result['ledger_snapshot']==review['terminal_ledger']
        and len(result['attempts'])==4 and [a['terminal'] for a in result['attempts']]==[a[-1] for a in gg],'r2 preserved combined result')
    bad=review['invalid_attempt'];ctx=reader.read(bad['context']);rec=reader.read(bad['receipt'])
    runtime={'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']}
    w.require(bad['attempt_id']==FAILED and bad['retry_of']==ORIGINAL_FAILED and bad['outcome_valid'] is False and bad['main_exit_code']==0
        and reader.read(bad['attempt_result'])==final and ctx['schema']=='n23-metered-worker-context-v1'
        and ctx['attempt_id']==FAILED and ctx['episode_key']==row['episode_key'] and ctx['profile']=='N30'
        and ctx['source']==source and ctx['plan']==review['plan'] and ctx['runtime']==runtime
        and rec['schema']=='n23-in-worker-audit-receipt-v1' and rec['attempt_id']==FAILED and rec['episode_key']==row['episode_key'] and rec['profile']=='N30'
        and rec['context']==bad['context'] and rec['source']==source and rec['plan']==review['plan'] and rec['runtime']==runtime
        and rec['accepted'] is False and rec['main_exit_code']==0 and rec['process_unchanged'] is True
        and rec['worker_error_type']=='ValueError' and rec['audit_report'] is None and rec['evidence'] is None,'r2 rejected receipt/context unchanged')
    return {**h,'events':events,'old_seconds':OLD_SECONDS,'r1_source':source,'r1_review':review,
        'r1_review_ref':release['closed_r1_execution_review'],'repair_review':repair,'repair_review_ref':release['accepted_repair_review'],
        'refs':[{'path':p,'sha256':s} for p,s in sorted(reader.refs.items())],
        'metadata_bytes_observed':reader.bytes,
        'historical_trust':h['historical_trust']+' R1 error classification/process closure and repaired-source online-byte parity rely on exact root reviews. No runner log/tensor/offline replay is read; rejected r1 receipt never becomes accepted.'}


def release_path(h):
    # Exact original review path is present in the r1 parser's bound references.
    paths=[x['path'] for x in h['refs'] if x['sha256']==original.REVIEW_SHA]
    w.require(len(paths)==1,'r2 original review ref ambiguity');return paths[0]


def current_subset(h,events):
    w.require([e for e in events if e.get('identity',{}).get('iteration') in {OLD,R1}]==h['events'],'r2 later/mutated original/r1 reservation')


def source_paths(root):
    root=Path(root);base=json.loads((root/DOC/'base-source-v1.json').read_text());paths={x['path'] for x in base['files']}
    for pattern in ('scripts/qd_ed_n30_r2_*.py','tests/test_n30_r2*.py','tests/n30_r2*.py',DOC+'/*'):
        paths.update(str(p.relative_to(root)) for p in root.glob(pattern) if p.is_file())
    return paths


def reverse_source(root,source):
    root=Path(root);base=json.loads((root/DOC/'base-source-v1.json').read_text());patch=json.loads((root/DOC/'reverse-source-v1.json').read_text())
    index={x['path']:x['sha256'] for x in source['files']}
    w.require(base['commit']==BASE and patch['base_commit']==BASE and set(index)==source_paths(root) and len(index)==len(source['files']) and set(patch['files'])==CHANGED,'r2 source closure')
    for f in base['files']:
        data=(root/f['path']).read_bytes();w.require(hashlib.sha256(data).hexdigest()==index[f['path']],'r2 source bytes')
        if f['path'] in CHANGED:
            e=patch['files'][f['path']];w.require(e['old_sha256']==f['sha256'] and e['new_sha256']==index[f['path']],'r2 reversal hashes')
            lines=data.decode().splitlines(keepends=True)
            for h in reversed(e['hunks']):
                w.require(lines[h['start']:h['end']]==h['new'],'r2 reverse hunk');lines[h['start']:h['end']]=h['old']
            data=''.join(lines).encode()
        w.require(hashlib.sha256(data).hexdigest()==f['sha256'],'r2 unauthorized prior source change')
    return base


def build(source,runtime,root):
    w.verify_source(root,source);base=reverse_source(root,source);h=history(root)
    w.require(runtime=={'path':h['plan']['runtime_manifest_path'],'sha256':h['plan']['runtime_manifest_sha256']},'r2 runtime unchanged')
    return {'schema':'n30-r2-source-history-bridge-v1','source':source,'repair_base_source':base,'original_source':h['source'],
        'r1_source':h['r1_source'],'runtime':runtime,'metadata_refs':h['refs'],'imports':h['imports'],'old_gpu_seconds':h['old_seconds'],
        'original_disposition':'INVALID_OR_INTERRUPTED','r1_disposition':'INVALID_OR_INTERRUPTED',
        'invalid_attempts':[ORIGINAL_FAILED,FAILED],'r1_review':h['r1_review_ref'],'repair_review':h['repair_review_ref'],
        'historical_trust':h['historical_trust'],'new_standalone_proof':False,'gpu_release':False}
