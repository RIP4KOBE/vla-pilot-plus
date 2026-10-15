"""Bounded immutable N26 closure attestation; no historical controller/proof replay."""
import hashlib,json
from pathlib import Path
from scripts import qd_ed_n23_worker as w
BASE='6026794cd5d52f3a5054bf2704ebb3c516f9f47e'
CHANGED=('core/rdt_policy_steer.py','scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py')
MAX_FILE=2*1024*1024

def bounded(reference):
    p=Path(reference['path'])
    w.require(p.is_absolute() and p.is_file() and not p.is_symlink() and p.stat().st_size<=MAX_FILE,'N27 closed metadata unsafe/large')
    with p.open('rb') as f:data=f.read(MAX_FILE+1)
    w.require(len(data)<=MAX_FILE and hashlib.sha256(data).hexdigest()==reference['sha256'],'N27 closed metadata changed')
    return json.loads(data)


def closed_records(root):
    folder=Path(root)/'experiments/qd_ed_n27'
    refs=json.loads((folder/'accepted-predecessor-refs-v1.json').read_text())
    w.require(set(refs)=={'review','result','source','plan','budget'},'N27 bounded predecessor roles differ')
    records={k:bounded(v) for k,v in refs.items()}
    review,result,source,plan,budget=(records[k] for k in ('review','result','source','plan','budget'))
    w.require(review.get('schema')=='n26-root-terminal-review-v1' and review.get('decision')=='ACCEPT_TERMINAL_RECONSTRUCTION'
        and review.get('cohort_disposition')==result.get('decision')=='REJECT_NUMERIC_FUTILITY'
        and review.get('accepted_cells')==result.get('audited_cells')==24
        and all(review.get(k)==refs[k] for k in ('result','source','plan'))
        and source.get('commit')==result.get('source_commit')==plan.get('source_commit')==BASE
        and len(source.get('files',[]))==315 and source['files']==plan['code_files']
        and review.get('cleanup',{}).get('downstream_cleanup_gate_satisfied') is True
        and result.get('dev_gate_promoted') is False
        and result.get('controller_evidence',{}).get('consistent') is True,
        'N27 accepted immutable N26 closure differs; INVALID/promotion cannot admit')
    w.require(source==json.loads((folder/'accepted-n26-source-v1.json').read_text())
        and budget.get('schema')=='n26-finite-budget-authority-v1','N27 source/budget identity differs')
    # Do NOT follow source proof/runtime/attempt refs: accepted independent root review is the historical attestation.
    return records


def source_paths(root):
    root=Path(root);old=json.loads((root/'experiments/qd_ed_n27/accepted-n26-source-v1.json').read_text())
    paths={v['path'] for v in old['files']}
    for pattern in ('scripts/qd_ed_n27_*.py','core/qd_feasible_ray*.py','configs/qd_ed_final/candidate_n27.json',
                    'tests/test_n27*.py','tests/n27_*.py','docs/n27*.md','experiments/qd_ed_n27/*'):
        paths.update(str(p.relative_to(root)) for p in root.glob(pattern) if p.is_file())
    return paths


def reverse_source(root,source):
    root=Path(root);old=json.loads((root/'experiments/qd_ed_n27/accepted-n26-source-v1.json').read_text())
    patch=json.loads((root/'experiments/qd_ed_n27/reverse-source-v1.json').read_text())
    w.require(patch['base_commit']==BASE and set(patch['files'])==set(CHANGED),'N27 reverse allowlist differs')
    indexed={v['path']:v['sha256'] for v in source['files']}
    w.require(set(indexed)==source_paths(root),'N27 source manifest scope differs')
    for item in old['files']:
        path=item['path'];data=(root/path).read_bytes()
        w.require(hashlib.sha256(data).hexdigest()==indexed[path],'N27 live source byte drift')
        if path in CHANGED:
            entry=patch['files'][path]
            w.require(indexed[path]==entry['new_sha256'] and item['sha256']==entry['old_sha256'],'N27 reverse identity differs')
            lines=data.decode().splitlines(keepends=True)
            for h in reversed(entry['hunks']):
                w.require(lines[h['start']:h['end']]==h['new'],'N27 reverse inserted bytes differ')
                lines[h['start']:h['end']]=h['old']
            data=''.join(lines).encode()
        w.require(hashlib.sha256(data).hexdigest()==item['sha256'],'N27 forbidden old source change')
    fixed=json.loads((root/'experiments/qd_ed_n27/phase-a-bytes-v1.json').read_text())
    for path,sha in fixed.items():w.require(w.sha(root/path)==sha,'N27 accepted Phase A changed')
    return {'original_source':old,'changed_existing':list(CHANGED),'reverse_patch':{'path':str(root/'experiments/qd_ed_n27/reverse-source-v1.json'),'sha256':w.sha(root/'experiments/qd_ed_n27/reverse-source-v1.json')},
            'unchanged_original_files':len(old['files'])-len(CHANGED),'phase_a_files':fixed}


def build(source,runtime,root):
    from scripts import qd_ed_n27_contract as c
    for module in (w,c):w.require(Path(module.__file__).resolve().is_relative_to(Path(root).resolve()),'N27 bridge module shadow')
    w.verify_source(root,source)
    closed=closed_records(root);delta=reverse_source(root,source)
    expected_runtime={'path':closed['plan']['runtime_manifest_path'],'sha256':closed['plan']['runtime_manifest_sha256']}
    w.require(runtime==expected_runtime,'N27 inherited runtime reference differs')
    refs=json.loads((Path(root)/'experiments/qd_ed_n27/accepted-predecessor-refs-v1.json').read_text())
    return {'schema':'n27-source-equivalence-bridge-v1','new_source':source,'runtime':runtime,'predecessor_refs':refs,**delta,
      'historical_trust':'Accepted immutable N26 terminal/root review attests old audits and settled proof. No old controller or proof is rerun.',
      'fresh_checks':'Current source, runtime bytes, resource, provider and complete private ledger remain live admission checks.',
      'gpu_release':False}


def verify(reference,source,runtime,root):
    record=w.read_ref(reference)
    w.require(record==build(source,runtime,root),'N27 source bridge differs')
    return record
