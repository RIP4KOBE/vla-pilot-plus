"""Root independent N29 byte/commit/source review; no research imports or tensors."""
from pathlib import Path
import argparse,ast,datetime,hashlib,json,subprocess,time
V=Path(__file__).resolve().parent;I=V/'implementation';start=time.process_time()
parser=argparse.ArgumentParser();parser.add_argument('--expected-commit',required=True);parser.add_argument('--manifest',type=Path,required=True);args=parser.parse_args()
def sha(b):return hashlib.sha256(b).hexdigest()
def ref(p):return {'path':str(p),'sha256':sha(p.read_bytes())}
def git(*a):return subprocess.check_output(['git',*a],cwd=I)
manifest=args.manifest.resolve();assert manifest.is_relative_to(V) and manifest.is_file()
source=json.loads(manifest.read_text());assert source['commit']==args.expected_commit
assert git('rev-parse','HEAD').decode().strip()==source['commit'] and git('status','--porcelain')==b''
records=source['files'];paths=[r['path'] for r in records]
assert len(paths)==len(set(paths)) and paths==sorted(paths)
assert sha(json.dumps(records,sort_keys=True,separators=(',',':'),allow_nan=False).encode())==source['sha256']
old=json.loads((I/'experiments/qd_ed_n29/base-source-v1.json').read_text())
assert old['commit']=='52b9eb0a8a365ee2ea12daffdb7a98c76bec0a72' and len(old['files'])==383
assert sha(json.dumps(old['files'],sort_keys=True,separators=(',',':'),allow_nan=False).encode())==old['sha256']
objects={}
for entry in git('ls-tree','-r','-z','HEAD').split(b'\0'):
    if entry:
        meta,name=entry.split(b'\t',1);mode,kind,oid=meta.split();objects[name.decode()]=(mode,kind,oid.decode())
for row in records:
    relative=Path(row['path']);p=I/relative
    assert not relative.is_absolute() and '..' not in relative.parts
    assert p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(I)
    assert relative.name!='2026-08-10-eds-qd-stage-guidance-transition-design.md'
    raw=p.read_bytes();assert sha(raw)==row['sha256']
    mode,kind,oid=objects[row['path']]
    assert kind==b'blob' and mode in (b'100644',b'100755')
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==oid
changed={'core/rdt_policy_steer.py','scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py'}
delta={line.split('\t',1)[1]:line.split('\t',1)[0] for line in git('diff','--name-status',old['commit'],'HEAD').decode().splitlines()}
oldnames={x['path'] for x in old['files']}
assert {p for p in delta if p in oldnames}==changed
assert all(status==('M' if p in changed else 'A') for p,status in delta.items())
assert set(paths)==oldnames|set(delta)
reverse=json.loads((I/'experiments/qd_ed_n29/reverse-source-v1.json').read_text())
assert set(reverse['files'])==changed and reverse['base_commit']==old['commit']
unchanged=0
for row in old['files']:
    raw=(I/row['path']).read_bytes()
    if row['path'] in changed:
        item=reverse['files'][row['path']]
        assert item['new_sha256']==sha(raw) and item['old_sha256']==row['sha256']
        lines=raw.decode().splitlines(keepends=True)
        for h in reversed(item['hunks']):
            assert lines[h['start']:h['end']]==h['new']
            lines[h['start']:h['end']]=h['old']
        raw=''.join(lines).encode()
        assert raw==git('show',old['commit']+':'+row['path'])
    else:unchanged+=1
    assert sha(raw)==row['sha256']
assert unchanged==380
oldtext=git('show',old['commit']+':core/rdt_policy_steer.py').decode()
newtext=(I/'core/rdt_policy_steer.py').read_text()
def methods(text):
    cls=next(n for n in ast.parse(text).body if isinstance(n,ast.ClassDef) and n.name=='RDTSteer')
    return {n.name:n for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
a,b=methods(oldtext),methods(newtext);assert set(a)==set(b)
different=[name for name in a if ast.get_source_segment(oldtext,a[name])!=ast.get_source_segment(newtext,b[name])]
before=a['_eds_renoise_reference'];after=b['_eds_renoise_reference']
observer='self._n29_rbf_witness.observe_renoise_input(population_trajectories, t)'
assert sum(ast.unparse(x)==observer for x in after.body)==1
assert [ast.dump(n,include_attributes=False) for n in before.body]==[ast.dump(n,include_attributes=False) for n in after.body if ast.unparse(n)!=observer]
n28=json.loads((I/'configs/qd_ed_final/candidate_n28.json').read_text());n29=json.loads((I/'configs/qd_ed_final/candidate_n29.json').read_text())
assert n29['profile']=={**n28['profile'],'diversity_update_mode':'population_relative_trust_v1'}
assert n29['parent_candidate']['sha256']==sha((I/'configs/qd_ed_final/candidate_n28.json').read_bytes())
assert sha((I/'core/qd_population_relative_trust.py').read_bytes())=='84d629a7d224c51dabe2d8bd962d887debbdc8a7468d72c20e0255134d08150b'
assert sha((I/'core/qd_feasible_ray_update.py').read_bytes())=='146163977866af87d2c643b0446be9ebac12f83cf9337d534b736874c623203e'
result={'schema':'n29-root-independent-source-review-v1','reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
'decision':'ACCEPT_SOURCE_BYTE_SCOPE','source':ref(manifest),'commit':source['commit'],
'files_verified':len(records),'files_verified_against_git_blobs':len(records),'old_files_unchanged':unchanged,
'changed_existing':sorted(changed),'new_files':len(set(paths)-oldnames),'reverse_verified_against_git_base':True,
'rdt_methods':len(a),'rdt_methods_byte_unchanged':len(a)-len(different),'rdt_changed_methods':different,
'original_renoise_numerical_body_ast_unchanged':True,'phase_a_helper_byte_unchanged':True,
'candidate_profile_sole_delta':{'diversity_update_mode':'population_relative_trust_v1'},
'fixed_model_score_budget':'21model batches;176canonical candidates/11score batches per complete guided chunk',
'rbf_calls':'N29 and N28 each14 per guided chunk; added scale reductions and actual episode compute are reported separately',
'provider_policy_unchanged':True,'provider_policy_source_sha256':sha((I/'core/codex_stage_policy.py').read_bytes()),
'gpu_proof_replaced_by_this_review':False,'gpu_dispatch_authorized':False,'gpu_model_api_sim_calls':0,'tensor_payload_reads':0,
'limitations':'Source/byte review only. CPU tests, runtime, metered CUDA proof, finite budget adoption and exact execution release remain separate checks.',
'review_cpu_seconds':time.process_time()-start}
output=V/'root-source-review-execution-v1.json'
with output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({k:result[k] for k in ('decision','files_verified','old_files_unchanged','new_files','rdt_methods_byte_unchanged','rdt_methods','rdt_changed_methods','review_cpu_seconds')}))

