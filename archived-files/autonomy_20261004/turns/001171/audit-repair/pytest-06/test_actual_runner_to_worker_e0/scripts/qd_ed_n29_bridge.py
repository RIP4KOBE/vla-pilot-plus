"""Finite current-source bridge; six accepted historical JSONs, no raw replay."""
import hashlib,json
from pathlib import Path
from scripts import qd_ed_n23_worker as w
BASE='52b9eb0a8a365ee2ea12daffdb7a98c76bec0a72'
CHANGED={'core/rdt_policy_steer.py','scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py'}
DOC='experiments/qd_ed_n29'
MAX_FILE=2*1024*1024


def bounded(reference):
    p=Path(reference['path']);w.require(p.is_absolute() and not p.is_symlink() and p.is_file() and p.stat().st_size<=MAX_FILE,'N29 metadata path/size')
    with p.open('rb') as f:data=f.read(MAX_FILE+1)
    w.require(len(data)<=MAX_FILE and hashlib.sha256(data).hexdigest()==reference['sha256'],'N29 closed metadata drift')
    return json.loads(data)


def closed_records(root):
    refs=json.loads((Path(root)/DOC/'accepted-history-refs-v1.json').read_text())
    w.require(set(refs)=={'review','source','plan','bridge','proof','original_dev_plan'},'N29 bounded historical roles')
    records={k:bounded(v) for k,v in refs.items()}
    review,old,plan,bridge,proof=(records[k] for k in ('review','source','plan','bridge','proof'))
    w.require(review.get('schema')=='n28-root-terminal-review-v1' and review.get('decision')=='REJECT_SCREEN'
        and review.get('source_commit')==BASE and review.get('source_files_rehashed')==383
        and review.get('audited_cells')==review.get('dispatched')==16 and review.get('invalid_attempts')==[]
        and review.get('controller_original_process_exited') is True
        and len(set(review.get('worker_original_processes_exited',[])))==16 and review.get('plan')==refs['plan']
        and review.get('counts')=={'C0':{'audited':4,'success':0},'Q0':{'audited':4,'success':0},
          'N27':{'audited':4,'success':1},'N28':{'audited':4,'success':0}},'N29 N28 closed review differs')
    w.require(old==json.loads((Path(root)/DOC/'base-source-v1.json').read_text()) and old['commit']==BASE
        and len(old['files'])==383 and plan['source_commit']==BASE and plan['code_files']==old['files']
        and bridge.get('schema')=='n28-source-equivalence-bridge-v1' and bridge.get('new_source')==old
        and proof.get('schema')=='n28-metered-tensor-proof-v1' and proof.get('accepted') is True and proof['source']==old
        and proof['runtime']==bridge['runtime']=={'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']},
        'N29 immutable N28 source/proof lineage differs')
    dev=records['original_dev_plan']
    w.require(dev.get('frozen') is True and len(dev['episodes'])==40
        and [(r['task_id'],r['profile']) for r in dev['episodes']]==[(t,a) for t in range(10) for a in ('C0','Q0','N7','N23')]
        and all(r['split']==r['seed_block']=='dev' for r in dev['episodes']),'N29 original10 Dev mapping differs')
    return records


def source_paths(root):
    root=Path(root);old=json.loads((root/DOC/'base-source-v1.json').read_text())
    paths={x['path'] for x in old['files']}
    for pattern in ('scripts/qd_ed_n29_*.py','core/qd_population_relative*.py','configs/qd_ed_final/candidate_n29.json',
                    'tests/test_n29*.py','tests/test_qd_population_relative_trust.py','docs/experiments/n29*','tests/n29*.py','docs/01_specs/n29*',DOC+'/*'):
        paths.update(str(p.relative_to(root)) for p in root.glob(pattern) if p.is_file())
    return paths


def reverse_source(root,source):
    root=Path(root);old=json.loads((root/DOC/'base-source-v1.json').read_text());patch=json.loads((root/DOC/'reverse-source-v1.json').read_text())
    index={x['path']:x['sha256'] for x in source['files']}
    w.require(set(index)==source_paths(root) and len(index)==len(source['files']) and patch['base_commit']==BASE
      and set(patch['files'])==CHANGED,'N29 complete source/reversal allowlist differs')
    for row in old['files']:
        path=row['path'];data=(root/path).read_bytes();w.require(hashlib.sha256(data).hexdigest()==index[path],'N29 live source drift')
        if path in CHANGED:
            entry=patch['files'][path];w.require(entry['new_sha256']==index[path] and entry['old_sha256']==row['sha256'],'N29 reverse hash differs')
            lines=data.decode().splitlines(keepends=True)
            for h in reversed(entry['hunks']):
                w.require(lines[h['start']:h['end']]==h['new'],'N29 reverse bytes differ');lines[h['start']:h['end']]=h['old']
            data=''.join(lines).encode()
        w.require(hashlib.sha256(data).hexdigest()==row['sha256'],'N29 unapproved old-source change '+path)
    return old


def build(source,runtime,root):
    w.verify_source(root,source);old=reverse_source(root,source);records=closed_records(root)
    w.require(runtime==records['proof']['runtime'],'N29 frozen runtime ref differs')
    return {'schema':'n29-source-equivalence-bridge-v1','new_source':source,'base_source':old,'runtime':runtime,
       'accepted_history_refs':json.loads((Path(root)/DOC/'accepted-history-refs-v1.json').read_text()),
       'changed_existing':sorted(CHANGED),'unchanged_old_files':len(old['files'])-len(CHANGED),
       'historical_trust':'Root accepted N28 closure/source bridge attests closed N28/N27 controls and prior native proofs. No raw evidence or recursive historical replay.',
       'new_proof_required':'Independent population-relative FP32 formula/cast and new wrapper; historical proof does not prove new math','gpu_release':False}


def verify(reference,source,runtime,root):
    result=w.read_ref(reference);w.require(result==build(source,runtime,root),'N29 source bridge differs');return result
