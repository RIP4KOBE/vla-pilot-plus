"""Finite current-source bridge; three accepted historical JSONs plus a runtime hash reference, no raw replay."""
import hashlib,json
from pathlib import Path
from scripts import qd_ed_n23_worker as w
BASE='6292fc8cffad2eec0f789e023d835ad3c1df146a'
PHASE_A='d6de4b4fecc2784d1f7a6b4d4b93d451b09a79d0'
CHANGED={'main.py','core/rdt_policy_steer.py','scripts/audit_decision_evidence.py','configs/config.yaml',
         'scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py'}
DOC='docs/experiments/n31'
MAX_FILE=2*1024*1024


def bounded(reference):
    p=Path(reference['path']);w.require(p.is_absolute() and not p.is_symlink() and p.is_file() and p.stat().st_size<=MAX_FILE,'N31 metadata path/size')
    with p.open('rb') as f:data=f.read(MAX_FILE+1)
    w.require(len(data)<=MAX_FILE and hashlib.sha256(data).hexdigest()==reference['sha256'],'N31 closed metadata drift')
    return json.loads(data)


def closed_records(root):
    refs=json.loads((Path(root)/DOC/'historical-input-bindings-v1.json').read_text())
    records={k:bounded(refs[k]) for k in ('closed_review','old_source','source_plan')}
    review,old,plan=(records[k] for k in ('closed_review','old_source','source_plan'))
    w.require(old==json.loads((Path(root)/DOC/'base-source-v1.json').read_text())
        and old['commit']==BASE and len(old['files'])==480,'N31 historical source manifest differs')
    w.require(review['schema']=='n30-r2-root-terminal-review-v1' and review['decision']=='REJECT_NUMERIC_DEV_FUTILITY'
        and review['source_commit']==BASE and review['source_files_rehashed']==480
        and review['plan']==refs['source_plan'] and review['new_dispatched']==4 and review['combined_dispatched']==8
        and review['audited_cells']==6 and review['counts']=={a:{'audited':2,'success':0} for a in ('C0','Q0','N30')}
        and review['new_invalid_attempts']==[] and len(review['preserved_original_invalids'])==2
        and all(review[k] is True for k in ('controller_original_process_exited','monitor_original_process_exited','all_new_workers_original_process_exited'))
        and review['budget_snapshot']['dispatched']==403
        and review['budget_snapshot']['gpu_hours_consumed']==53.80872756284531,'N31 predecessor root closure differs')
    w.require(plan==json.loads((Path(root)/DOC/'base-plan-metadata-v1.json').read_text())
        and plan['source_commit']==BASE and plan['code_files']==old['files'] and plan['frozen'] is True
        and {'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']}==refs['runtime'],
        'N31 old plan/source/runtime reference differs')
    return records


def source_paths(root):
    root=Path(root);old=json.loads((root/DOC/'base-source-v1.json').read_text())
    paths={x['path'] for x in old['files']}
    for pattern in ('scripts/qd_ed_n31_*.py','core/qd_capture_dwell*.py','configs/qd_ed_final/candidate_n31.json',
                    'configs/qd_ed_final/n31_dev_task_identities.json','tests/test_n31*.py','tests/n31*.py',
                    'tests/n31_original_methods.json','tests/test_qd_capture_dwell_proposal.py','docs/experiments/n31_*.md',DOC+'/*'):
        paths.update(str(p.relative_to(root)) for p in root.glob(pattern) if p.is_file())
    return paths


def reverse_source(root,source):
    root=Path(root);old=json.loads((root/DOC/'base-source-v1.json').read_text());patch=json.loads((root/DOC/'reverse-source-v1.json').read_text())
    index={x['path']:x['sha256'] for x in source['files']}
    w.require(set(index)==source_paths(root) and len(index)==len(source['files']) and patch['base_commit']==BASE
      and set(patch['files'])==CHANGED,'N31 complete source/reversal allowlist differs')
    for row in old['files']:
        path=row['path'];data=(root/path).read_bytes();w.require(hashlib.sha256(data).hexdigest()==index[path],'N31 live source drift')
        if path in CHANGED:
            entry=patch['files'][path];w.require(entry['new_sha256']==index[path] and entry['old_sha256']==row['sha256'],'N31 reverse hash differs')
            lines=data.decode().splitlines(keepends=True)
            for h in reversed(entry['hunks']):
                w.require(lines[h['start']:h['end']]==h['new'],'N31 reverse bytes differ');lines[h['start']:h['end']]=h['old']
            data=''.join(lines).encode()
        w.require(hashlib.sha256(data).hexdigest()==row['sha256'],'N31 unapproved old-source change '+path)
    return old


def build(source,runtime,root):
    w.verify_source(root,source);old=reverse_source(root,source);records=closed_records(root)
    w.require(runtime==json.loads((Path(root)/DOC/'historical-input-bindings-v1.json').read_text())['runtime'],'N31 frozen runtime ref differs')
    return {'schema':'n31-source-equivalence-bridge-v1','new_source':source,'base_source':old,'runtime':runtime,
       'accepted_history_refs':json.loads((Path(root)/DOC/'historical-input-bindings-v1.json').read_text()),
       'changed_existing':sorted(CHANGED),'unchanged_old_files':len(old['files'])-len(CHANGED),
       'historical_trust':'Hash-bound root N30 R2 closure and source manifest attest old evidence and proofs; no raw evidence or recursive historical replay. New episodes are fresh, without inherited outcomes.',
       'phase_a_commit':PHASE_A,'new_standalone_proof':False,'new_evidence':'Profile-bound independent binary64 prism and native assignment audit inside each metered worker; historical proof does not certify this operation','gpu_release':False}


def verify(reference,source,runtime,root):
    result=w.read_ref(reference);w.require(result==build(source,runtime,root),'N31 source bridge differs');return result
