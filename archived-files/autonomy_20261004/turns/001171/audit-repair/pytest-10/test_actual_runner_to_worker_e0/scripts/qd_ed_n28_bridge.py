"""Finite current-source bridge; four accepted historical JSONs, no raw replay."""
import hashlib,json
from pathlib import Path
from scripts import qd_ed_n23_worker as w
BASE='e21d48ab33dbd3aca017349b6004c2ba7d981493'
CHANGED={'configs/config.yaml','core/rdt_policy_steer.py','scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py'}
DOC='experiments/qd_ed_n28'
MAX_FILE=2*1024*1024


def bounded(reference):
    p=Path(reference['path']);w.require(p.is_absolute() and not p.is_symlink() and p.is_file() and p.stat().st_size<=MAX_FILE,'N28 metadata path/size')
    with p.open('rb') as f:data=f.read(MAX_FILE+1)
    w.require(len(data)<=MAX_FILE and hashlib.sha256(data).hexdigest()==reference['sha256'],'N28 closed metadata drift')
    return json.loads(data)


def closed_records(root):
    refs=json.loads((Path(root)/DOC/'accepted-history-refs-v1.json').read_text())
    w.require(set(refs)=={'review','plan','bridge','proof'},'N28 exact historical roles')
    records={k:bounded(v) for k,v in refs.items()};review,plan,bridge,proof=(records[k] for k in ('review','plan','bridge','proof'))
    w.require(review.get('schema')=='n27-hydra-root-terminal-review-v1' and review.get('decision')=='ACCEPT_TERMINAL_RECONSTRUCTION'
      and review.get('cohort_disposition')=='REJECT_SCREEN' and review.get('new_valid_cells')==13
      and review.get('imported_valid_cells')==3 and review.get('all_dispatched_attempts')==17
      and review.get('controller_and_all_16_accepted_workers_exited') is True
      and review.get('original_invalid_retained')=='rdt-qd-ed-final-20260921T093925Z__n27_screen_t00_n27_20261001__1af7d45d9a10'
      and review.get('counts')=={a:{'audited':4,'success':0} for a in ('C0','Q0','N26','N27')},'N28 accepted N27 closure differs')
    old=json.loads((Path(root)/DOC/'base-source-v1.json').read_text())
    w.require(bridge.get('schema')=='n27-hydra-source-bridge-v1' and bridge.get('new_source')==old and old['commit']==BASE
      and bridge.get('reverse_exact') is True and bridge.get('historical_backend_proof')==refs['proof']
      and proof.get('schema')=='n27-metered-tensor-proof-v1' and proof.get('accepted') is True
      and proof['source']['commit']==plan['source_commit']=='095cfeecd6af55477d2529441c307ab712e8a8da'
      and proof['source']['files']==plan['code_files'] and proof['runtime']==bridge['runtime']=={
       'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']},'N28 old source/proof lineage differs')
    return records


def source_paths(root):
    root=Path(root);old=json.loads((root/DOC/'base-source-v1.json').read_text())
    paths={x['path'] for x in old['files']}
    for pattern in ('scripts/qd_ed_n28_*.py','core/qd_parent_before_renoise.py','configs/qd_ed_final/candidate_n28.json',
                    'tests/test_n28*.py','tests/n28*.py','docs/01_specs/n28*',DOC+'/*'):
        paths.update(str(p.relative_to(root)) for p in root.glob(pattern) if p.is_file())
    return paths


def reverse_source(root,source):
    root=Path(root);old=json.loads((root/DOC/'base-source-v1.json').read_text());patch=json.loads((root/DOC/'reverse-source-v1.json').read_text())
    index={x['path']:x['sha256'] for x in source['files']}
    w.require(set(index)==source_paths(root) and len(index)==len(source['files']) and patch['base_commit']==BASE
      and set(patch['files'])==CHANGED,'N28 complete source/reversal allowlist differs')
    for row in old['files']:
        path=row['path'];data=(root/path).read_bytes();w.require(hashlib.sha256(data).hexdigest()==index[path],'N28 live source drift')
        if path in CHANGED:
            entry=patch['files'][path];w.require(entry['new_sha256']==index[path] and entry['old_sha256']==row['sha256'],'N28 reverse hash differs')
            lines=data.decode().splitlines(keepends=True)
            for h in reversed(entry['hunks']):
                w.require(lines[h['start']:h['end']]==h['new'],'N28 reverse bytes differ');lines[h['start']:h['end']]=h['old']
            data=''.join(lines).encode()
        w.require(hashlib.sha256(data).hexdigest()==row['sha256'],'N28 unapproved old-source change '+path)
    return old


def build(source,runtime,root):
    w.verify_source(root,source);old=reverse_source(root,source);records=closed_records(root)
    w.require(runtime==records['proof']['runtime'],'N28 frozen runtime ref differs')
    return {'schema':'n28-source-equivalence-bridge-v1','new_source':source,'base_source':old,'runtime':runtime,
       'accepted_history_refs':json.loads((Path(root)/DOC/'accepted-history-refs-v1.json').read_text()),
       'changed_existing':sorted(CHANGED),'unchanged_old_files':len(old['files'])-len(CHANGED),
       'historical_trust':'Root accepted N27 closure/source bridge attests prior proof and valid outcomes. No raw evidence or historical controller replay.',
       'new_proof_required':'parent wrapper and renoise boundary; old same-forward proof is not parent-origin evidence','gpu_release':False}


def verify(reference,source,runtime,root):
    result=w.read_ref(reference);w.require(result==build(source,runtime,root),'N28 source bridge differs');return result
