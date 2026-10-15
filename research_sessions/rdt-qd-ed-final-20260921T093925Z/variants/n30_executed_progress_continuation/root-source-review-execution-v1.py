"""Root independent N30 byte/source review. No model, simulator or payload loads."""
from pathlib import Path
import argparse,ast,datetime,hashlib,json,subprocess,time
V=Path(__file__).resolve().parent;I=V/'implementation';start=time.process_time()
p=argparse.ArgumentParser();p.add_argument('--commit',required=True);p.add_argument('--manifest',type=Path,required=True);args=p.parse_args()
def sha(b):return hashlib.sha256(b).hexdigest()
def ref(p):return {'path':str(p.resolve()),'sha256':sha(p.read_bytes())}
def git(*a):return subprocess.check_output(['git',*a],cwd=I)
source=json.loads(args.manifest.read_text())
assert source['commit']==args.commit==git('rev-parse','HEAD').decode().strip()
assert git('status','--porcelain')==b''
rows=source['files'];paths=[x['path'] for x in rows]
assert paths==sorted(set(paths))
assert sha(json.dumps(rows,sort_keys=True,separators=(',',':'),allow_nan=False).encode())==source['sha256']
old=json.loads((I/'docs/experiments/n30/base-source-v1.json').read_text())
assert old['commit']=='d855cfd690482e018bb40ce98edec80fad9700e0' and len(old['files'])==411
objects={}
for entry in git('ls-tree','-r','-z','HEAD').split(b'\0'):
    if entry:
        meta,name=entry.split(b'\t',1);mode,kind,oid=meta.split();objects[name.decode()]=(mode,kind,oid.decode())
for row in rows:
    rel=Path(row['path']);path=I/rel
    assert not rel.is_absolute() and '..' not in rel.parts
    assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(I)
    assert rel.name!='2026-08-10-eds-qd-stage-guidance-transition-design.md'
    raw=path.read_bytes();assert sha(raw)==row['sha256']
    mode,kind,oid=objects[row['path']]
    assert kind==b'blob' and mode in (b'100644',b'100755')
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==oid
changed={'main.py','core/rdt_policy_steer.py','core/eds_eval_metrics.py','configs/config.yaml','scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py'}
delta={line.split('\t',1)[1]:line.split('\t',1)[0] for line in git('diff','--name-status',old['commit'],'HEAD').decode().splitlines()}
oldnames={x['path'] for x in old['files']}
assert {x for x in delta if x in oldnames}==changed
assert all(status==('M' if name in changed else 'A') for name,status in delta.items())
assert set(paths)==oldnames|set(delta), {'missing':sorted((oldnames|set(delta))-set(paths)),'extra':sorted(set(paths)-(oldnames|set(delta)))}
reverse=json.loads((I/'docs/experiments/n30/reverse-source-v1.json').read_text())
assert reverse['base_commit']==old['commit'] and set(reverse['files'])==changed
for row in old['files']:
    raw=(I/row['path']).read_bytes()
    if row['path'] in changed:
        item=reverse['files'][row['path']];assert item['new_sha256']==sha(raw) and item['old_sha256']==row['sha256']
        lines=raw.decode().splitlines(keepends=True)
        for h in reversed(item['hunks']):
            assert lines[h['start']:h['end']]==h['new'];lines[h['start']:h['end']]=h['old']
        raw=''.join(lines).encode();assert raw==git('show',old['commit']+':'+row['path'])
    assert sha(raw)==row['sha256']
phase_a='9029b384a34343efd73b4ea02184d83c5e52de61'
oldhelper=ast.parse(git('show',phase_a+':core/qd_executed_progress.py').decode())
newhelper=ast.parse((I/'core/qd_executed_progress.py').read_text())
def without_config(tree):
    return ast.dump(ast.Module(body=[n for n in tree.body if not (isinstance(n,ast.FunctionDef) and n.name=='validate_config')],type_ignores=[]),include_attributes=False)
assert without_config(oldhelper)==without_config(newhelper)
profile=json.loads((I/'configs/qd_ed_final/candidate_n30.json').read_text())
base=json.loads((I/'configs/qd_ed_final/n4_observed_baseline_profiles.json').read_text())['profiles']['Q0']
assert profile['profile']=={**base['restored_profile'],'executed_progress_continuation_mode':'executed_progress_continuation_v1'}
assert profile['baseline_provenance']['sha256']==sha((I/'configs/qd_ed_final/n4_observed_baseline_profiles.json').read_bytes())
assert profile['profile'].get('executed_progress_continuation_control','none')=='none'
assert (I/'tests/n30_original_control_functions.json').read_bytes()==git('show',phase_a+':tests/n30_original_control_functions.json')
result={'schema':'n30-root-independent-source-review-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'decision':'ACCEPT_SOURCE_BYTE_SCOPE','source':ref(args.manifest),'commit':source['commit'],
 'files_verified':len(rows),'files_verified_against_git_blobs':len(rows),'old_files_unchanged':411-len(changed),
 'changed_existing':sorted(changed),'new_files':len(set(paths)-oldnames),'reverse_verified_against_git_base':True,
 'phase_a_progress_helper_unchanged_except_explicit_config_control':True,
 'default_off_control_fixture_unchanged':True,'candidate_profile_sole_delta':{'executed_progress_continuation_mode':'executed_progress_continuation_v1'},
 'future_qd_off_control_dispatched':False,'gpu_model_api_sim_calls':0,'tensor_payload_reads':0,
 'source_review_cpu_seconds':time.process_time()-start,'gpu_dispatch_authorized':False,
 'limitations':'Static source and committed byte identity; CPU integration tests and root operational admission are separate evidence. No efficacy claim.'}
out=V/'root-source-review-execution-v1.json'
with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(result))

