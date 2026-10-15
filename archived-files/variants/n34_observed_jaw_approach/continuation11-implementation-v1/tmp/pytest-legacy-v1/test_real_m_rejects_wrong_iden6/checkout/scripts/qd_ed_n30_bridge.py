"""Finite current-source bridge; four accepted historical JSONs, no raw replay."""
import hashlib,json
from pathlib import Path
from scripts import qd_ed_n23_worker as w
BASE='d855cfd690482e018bb40ce98edec80fad9700e0'
PHASE_A='9029b384a34343efd73b4ea02184d83c5e52de61'
CHANGED={'main.py','core/rdt_policy_steer.py','core/eds_eval_metrics.py','configs/config.yaml',
         'scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py'}
DOC='docs/experiments/n30'
MAX_FILE=2*1024*1024


def bounded(reference):
    p=Path(reference['path']);w.require(p.is_absolute() and not p.is_symlink() and p.is_file() and p.stat().st_size<=MAX_FILE,'N30 metadata path/size')
    with p.open('rb') as f:data=f.read(MAX_FILE+1)
    w.require(len(data)<=MAX_FILE and hashlib.sha256(data).hexdigest()==reference['sha256'],'N30 closed metadata drift')
    return json.loads(data)


def closed_records(root):
    refs=json.loads((Path(root)/DOC/'historical-input-bindings-v1.json').read_text())
    records={k:bounded(refs[k]) for k in ('closed_review','source_review','source_plan','budget_authority')}
    review,source_review,plan=(records[k] for k in ('closed_review','source_review','source_plan'))
    old=json.loads((Path(root)/DOC/'base-source-v1.json').read_text())
    w.require(review['schema']=='n29-root-terminal-review-v1' and review['decision']=='REJECT_NUMERIC_DEV_FUTILITY'
        and review['source_commit']==BASE and review['source_files_rehashed']==411
        and review['audited_cells']==review['dispatched']==24 and review['invalid_attempts']==[]
        and review['controller_original_process_exited'] is True and len(set(review['worker_original_processes_exited']))==24
        and review['plan']==refs['source_plan'] and review['counts']==refs['closed_result']['counts'],'N30 closed predecessor differs')
    w.require(source_review['schema']=='n29-source-runtime-review-v1' and source_review['disposition']=='accepted'
        and source_review['source']==old and old['commit']==BASE and len(old['files'])==411
        and old['sha256']==refs['source_record_sha256'] and source_review['runtime']==refs['runtime']
        and plan['code_files']==old['files'] and plan['source_commit']==BASE
        and plan['frozen'] is True and [(r['task_id'],r['profile']) for r in plan['episodes']]==[(t,a) for t in range(10) for a in ('C0','Q0','N28','N29')]
        and all(r['split']==r['seed_block']=='dev' for r in plan['episodes'])
        and {'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']}==refs['runtime'],
        'N30 closed source/runtime/Dev mapping differs')
    w.require(records['budget_authority']['caps']==refs['caps'],'N30 cumulative budget authority differs')
    return records


def source_paths(root):
    root=Path(root);old=json.loads((root/DOC/'base-source-v1.json').read_text())
    paths={x['path'] for x in old['files']}
    for pattern in ('scripts/qd_ed_n30_*.py','core/qd_executed_progress.py','configs/qd_ed_final/candidate_n30.json',
                    'tests/test_n30*.py','tests/n30*.py','tests/n30_original_control_functions.json',DOC+'/*'):
        paths.update(str(p.relative_to(root)) for p in root.glob(pattern) if p.is_file())
    return paths


def reverse_source(root,source):
    root=Path(root);old=json.loads((root/DOC/'base-source-v1.json').read_text());patch=json.loads((root/DOC/'reverse-source-v1.json').read_text())
    index={x['path']:x['sha256'] for x in source['files']}
    w.require(set(index)==source_paths(root) and len(index)==len(source['files']) and patch['base_commit']==BASE
      and set(patch['files'])==CHANGED,'N30 complete source/reversal allowlist differs')
    for row in old['files']:
        path=row['path'];data=(root/path).read_bytes();w.require(hashlib.sha256(data).hexdigest()==index[path],'N30 live source drift')
        if path in CHANGED:
            entry=patch['files'][path];w.require(entry['new_sha256']==index[path] and entry['old_sha256']==row['sha256'],'N30 reverse hash differs')
            lines=data.decode().splitlines(keepends=True)
            for h in reversed(entry['hunks']):
                w.require(lines[h['start']:h['end']]==h['new'],'N30 reverse bytes differ');lines[h['start']:h['end']]=h['old']
            data=''.join(lines).encode()
        w.require(hashlib.sha256(data).hexdigest()==row['sha256'],'N30 unapproved old-source change '+path)
    return old


def build(source,runtime,root):
    w.verify_source(root,source);old=reverse_source(root,source);records=closed_records(root)
    w.require(runtime==records['source_review']['runtime'],'N30 frozen runtime ref differs')
    return {'schema':'n30-source-equivalence-bridge-v1','new_source':source,'base_source':old,'runtime':runtime,
       'accepted_history_refs':json.loads((Path(root)/DOC/'historical-input-bindings-v1.json').read_text()),
       'changed_existing':sorted(CHANGED),'unchanged_old_files':len(old['files'])-len(CHANGED),
       'historical_trust':'Hash-bound root N29 closure and source/runtime review attest old evidence and proofs; no raw evidence or recursive historical replay. New episodes are fresh, without inherited outcomes.',
       'phase_a_commit':PHASE_A,'new_standalone_proof':False,'new_evidence':'Profile-bound CPU native copy/mask and float64 feedback replay inside each metered worker; historical proof does not certify this operation','gpu_release':False}


def verify(reference,source,runtime,root):
    result=w.read_ref(reference);w.require(result==build(source,runtime,root),'N30 source bridge differs');return result
