"""Read-only verification of this executor packet, never production admission."""
import argparse
import hashlib
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--report', required=True)
p.add_argument('--controller-proof')
p.add_argument('--controller-sha256')
args = p.parse_args()
report_path = Path(args.report)
report = json.loads(report_path.read_bytes())
def check(ref):
    path = Path(ref['path'])
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == ref['sha256'], str(path)
    if 'bytes' in ref:
        assert len(data) == ref['bytes'], str(path)
for ref in report['outputs'].values():
    check(ref)
for ref in report['input_hashes']:
    check(ref)
assert report['status'] == 'DISABLED_CANDIDATE_REFRESH_COMPLETE_PENDING_P3_P4'
assert report['source'] == 'f661a570403e9ff7224d4c35230a0f2b9321a269'
assert report['scientific_source'] == '1065f38122379a515b60a9a424f574330405b66f'
for k in ('release_enabled', 'source_adopted', 'gpu_authorized', 'provider_measurement_authorized', 'graph_complete', 'graph_verified'):
    assert report[k] is False, k
base = report_path.parent
graph = json.loads((base / 'graph.candidate-disabled-v1.json').read_bytes())
assert graph['resource_id'] is None
assert graph['authority'] is graph['b5_review'] is graph['root_acceptance'] is graph['root_controller_acceptance'] is None
assert graph['plan'] is graph['audit'] is graph['full40_manifests'] is None
runtime = json.loads((base / 'disabled-runtime.json').read_bytes())
assert runtime['preparation']['source'] == report['source']
assert runtime['preparation']['runtime_ready'] is runtime['provider_ready'] is runtime['cuda_egl_verified'] is False
controller = json.loads((base / 'controller-semantics.pending-disabled-v1.json').read_bytes())
assert controller['status'] == 'PENDING_ROOT_REVIEW_DISABLED' and controller['review_evidence'] == {}
print(json.dumps({'result': 'PASS_PACKET_HASHES_AND_DISABLED_BOUNDARIES', 'output_count': len(report['outputs']),
    'input_count': len(report['input_hashes']), 'production_admission': False,
    'report_sha256': hashlib.sha256(report_path.read_bytes()).hexdigest()}, sort_keys=True))

if args.controller_proof:
    # No witness or approval is generated; consume a separately supplied review.
    import ast, types, math, os, datetime
    auth = json.loads((base/'authority-v1.json').read_bytes())
    assert not any(os.path.lexists(x) for x in auth['stop_authority']['paths'])
    assert datetime.datetime.now(datetime.timezone.utc) < datetime.datetime.fromisoformat(auth['stop_authority']['deadline'].replace('Z','+00:00'))
    root=Path(report['worktree'])
    def functions(path,names,namespace):
        tree=ast.parse(path.read_bytes())
        selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
        assert {n.name for n in selected}==set(names)
        exec(compile(ast.Module(body=selected,type_ignores=[]),str(path),'exec'),namespace)
        return namespace
    worker=functions(root/'scripts/qd_ed_n23_worker.py',['require','sha','canonical_sha','read_ref'],dict(Path=Path,json=json,hashlib=hashlib))
    w=types.SimpleNamespace(**worker)
    tree=ast.parse((root/'scripts/qd_ed_n34_controller.py').read_bytes())
    fields=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FIELDS' for t in n.targets))
    ns=functions(root/'scripts/qd_ed_n34_controller.py',['verify_semantics'],dict(w=w,math=math,FIELDS=fields))
    review_ref={'path':args.controller_proof,'sha256':args.controller_sha256}
    closure=w.read_ref(graph['runtime_closure'])
    proof=ns['verify_semantics'](review_ref,graph['runtime'],closure)
    for key in ('class','module','source','instance','semantics'):
        assert proof[key]==controller[key], key
    # Production binding is runtime + closure module identity. Packet-level extra pins:
    assert proof.get('runtime_closure')==graph['runtime_closure']
    assert proof.get('source_commit')==report['source']
    print(json.dumps({'result':'PASS_EXACT_CONTROLLER_REVIEW_BINDING','review':review_ref,
        'candidate_graph':report['candidate_graph'],'independent_authorship_verified':False,
        'release_enabled':False},sort_keys=True))
