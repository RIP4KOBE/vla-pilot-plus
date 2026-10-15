from pathlib import Path
import ast,hashlib,json,subprocess,time,resource
V=Path(__file__).resolve().parent;I=V/'implementation';start=time.process_time();a=resource.getrusage(resource.RUSAGE_CHILDREN)
sha=lambda data:hashlib.sha256(data).hexdigest()
canonical=lambda data:sha(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
def write(name,obj):
 p=V/name
 with p.open('x') as f:f.write(json.dumps(obj,indent=2,allow_nan=False)+'\n')
 return {'path':str(p),'sha256':sha(p.read_bytes())}
def git(*args):return subprocess.check_output(['git',*args],cwd=I)
head=git('rev-parse','HEAD').decode().strip();assert head=='d855cfd690482e018bb40ce98edec80fad9700e0'
assert git('status','--porcelain')==b''
base=json.loads((I/'experiments/qd_ed_n29/base-source-v1.json').read_text())
paths={v['path'] for v in base['files']}
patterns=('scripts/qd_ed_n29_*.py','core/qd_population_relative*.py','configs/qd_ed_final/candidate_n29.json','tests/test_n29*.py','tests/test_qd_population_relative_trust.py','docs/experiments/n29*','tests/n29*.py','docs/01_specs/n29*','experiments/qd_ed_n29/*')
for pattern in patterns:paths.update(str(p.relative_to(I)) for p in I.glob(pattern) if p.is_file())
files=[]
for name in sorted(paths):
 p=I/name;assert not p.is_symlink() and p.resolve().is_relative_to(I);data=p.read_bytes();assert git('show',head+':'+name)==data
 files.append({'path':name,'sha256':sha(data)})
source={'commit':head,'files':files,'sha256':canonical(files)}
source_ref=write('source-manifest-execution-v1.json',source)
old={r['path']:r['sha256'] for r in base['files']};new={r['path']:r['sha256'] for r in files};changed=sorted(p for p in old if old[p]!=new[p]);added=sorted(set(new)-set(old))
assert changed==['core/rdt_policy_steer.py','scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py']
reverse=json.loads((I/'experiments/qd_ed_n29/reverse-source-v1.json').read_text())
for p in changed:
 data=(I/p).read_bytes();entry=reverse['files'][p];assert sha(data)==entry['new_sha256'];lines=data.decode().splitlines(keepends=True)
 for h in reversed(entry['hunks']):assert lines[h['start']:h['end']]==h['new'];lines[h['start']:h['end']]=h['old']
 restored=''.join(lines).encode();assert restored==git('show',base['commit']+':'+p) and sha(restored)==old[p]
phase_a=['core/qd_population_relative_trust.py','tests/test_qd_population_relative_trust.py','docs/experiments/n29-population-relative-trust-native-arithmetic-v1.md']
assert all((I/p).read_bytes()==git('show','427b98703938f4e2a14ff810ff56ed5b7bcbd715:'+p) for p in phase_a)
original=git('show',base['commit']+':core/rdt_policy_steer.py').decode();current=(I/'core/rdt_policy_steer.py').read_text()
def methods(s):
 cls=next(x for x in ast.parse(s).body if isinstance(x,ast.ClassDef) and x.name=='RDTSteer');lines=s.splitlines(keepends=True)
 return {x.name:''.join(lines[min([x.lineno,*[v.lineno for v in x.decorator_list]])-1:x.end_lineno]) for x in cls.body if isinstance(x,ast.FunctionDef)}
a0,a1=methods(original),methods(current)
bridge_summary={'schema':'n29-cpu-source-reversal-review-v1','base_commit':base['commit'],'new_commit':head,'old_source_files':len(old),'new_source_files':len(files),'unchanged_old_files':len(old)-len(changed),'changed_existing':changed,'added':added,'exact_reverse_verified':True,'phase_a_unchanged':phase_a,'rdt_method_count':len(a0),'rdt_methods_unchanged':sum(a1.get(k)==v for k,v in a0.items()),'rdt_changed_methods':[k for k,v in a0.items() if a1.get(k)!=v],'source_manifest':source_ref,'historical_raw_proof_replayed':False,'actual_runtime_loaded':False,'gpu_authorized':False}
write('source-reverse-summary-v1.json',bridge_summary)
(V/'source-diff-execution-v1.patch').write_bytes(git('diff',base['commit'],head,'--',*changed,*added))
# Parse constants only; do not import production modules, runtime, state or ledger.
tree=ast.parse((I/'scripts/qd_ed_n29_contract.py').read_text());constants={}
for node in tree.body:
 if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
  try:constants[node.targets[0].id]=ast.literal_eval(node.value)
  except (ValueError,TypeError):pass
btree=ast.parse((I/'scripts/qd_ed_n29_backend.py').read_text());limits=next(ast.literal_eval(n.value) for n in btree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='LIMITS')
ref=lambda p:{'path':str(p),'sha256':None}
protocol={'path':str(V/'execution-integration-cpu-scope-v1.md'),'sha256':constants['PROTOCOL_SHA']}
arithmetic={'path':str(V/'independent-arithmetic-protocol-v1.md'),'sha256':sha((V/'independent-arithmetic-protocol-v1.md').read_bytes())}
refs=json.loads((I/'experiments/qd_ed_n29/accepted-history-refs-v1.json').read_text())
# Only this already-authorized bounded public plan is read; no nested refs are followed.
planbytes=Path(refs['plan']['path']).read_bytes();assert sha(planbytes)==refs['plan']['sha256'];oldplan=json.loads(planbytes)
runtime={'path':oldplan['runtime_manifest_path'],'sha256':oldplan['runtime_manifest_sha256']}
budgetref=ref(V/'budget-adoption-v1/authority.json');bridgeref=ref(V/'source-equivalence-bridge-v1.json');proofref=ref(V/'arithmetic-preflight/proof-v1.json')
arithreview=ref(V/'arithmetic-preflight-source-review-v1.json');arithauth=ref(V/'arithmetic-preflight-adoption-v1/authority.json');finalreview=ref(V/'final-source-runtime-review-v1.json');devauth=ref(V/'adoption-v1/authority.json');planref=ref(V/'plan.frozen.v1.gpu7.json')
def template(path,document,missing):return {'intended_path':str(V/path),'executable':False,'requires_root_review_and_adoption':True,'unresolved':missing,'document':document}
templates=[]
templates.append(template('budget-adoption-v1/authority.json',{'schema':'n29-finite-budget-authority-v1','caps':constants['BASE_CAPS'],'protocol':protocol,'predecessor':refs['review'],'limits':constants['LIMITS'],'local_gpu_hours':13.5,'amendment':None,'recorded_at':None,'authority_interpretation':None,'validation_authorized':False,'formal_authorized':False},['amendment exact root record','recorded_at','authority_interpretation','actual locked state adoption']))
templates.append(template('source-equivalence-bridge-v1.json',None,['root bridge.build on integrated current source/runtime and exact accepted history']))
templates.append(template('arithmetic-preflight-source-review-v1.json',{'schema':'n29-arithmetic-source-review-v1','accepted':True,'source':source,'runtime':runtime,'source_bridge':bridgeref,'phase_b_protocol':protocol,'arithmetic_protocol':arithmetic,'predecessor':refs['review'],'budget_reuse':budgetref,'limits':limits,'gpu_release':False},['root source/runtime/bridge review','pending referenced hashes']))
templates.append(template('arithmetic-preflight-adoption-v1/authority.json',{'schema':'n29-arithmetic-resource-authority-v1','source':source,'runtime':runtime,'source_review':arithreview,'budget_reuse':budgetref,'limits':limits,'boot_id':None,'automatic_retry':False,'dev_authorized':False,'validation_authorized':False,'formal_authorized':False},['current boot','root private state n29_arithmetic_authority','pending hashes']))
templates.append(template('arithmetic-preflight-release-v1.json',{'schema':'n29-tensor-resource-release-v1','source':source,'runtime':runtime,'authority':arithauth,'limits':limits,'one_shot':True},['root concrete resource release after independent review/adoption']))
templates.append(template('final-source-runtime-review-v1.json',{'schema':'n29-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime,'protocol':protocol,'source_plan':refs['plan'],'source_bridge':bridgeref,'predecessor':refs['review'],'backend_proof':proofref,'arithmetic_protocol':arithmetic,'budget_reuse':budgetref,'no_gpu_release':True},['actual exact native arithmetic proof+metered terminal','root review','pending hashes']))
templates.append(template('adoption-v1/authority.json',{'schema':'n29-dev-authority-v1','cohort_id':constants['COHORT'],'source':source,'runtime':runtime,'protocol':protocol,'final_review':finalreview,'budget_reuse':budgetref,'limits':constants['LIMITS'],'local_gpu_hours':13.5,'recorded_at':None,'authority_interpretation':None,'predecessor':refs['review'],'validation_authorized':False,'formal_authorized':False},['root private n29_dev_authority','recorded_at','authority_interpretation','pending hashes']))
templates.append(template('execution-release-v1.json',{'schema':'n29-dev-execution-release-v1','plan':planref,'source_commit':head,'cohort_id':constants['COHORT'],'episode_keys':[f'n29_dev_t{t:02d}_{arm.lower()}_20261001' for t in range(10) for arm in constants['ARMS']],'authority':devauth,'physical_gpu':7,'limits':constants['LIMITS'],'validation_authorized':False,'formal_authorized':False},['actual frozen plan/hash','actual command/provider/source/capacity root check','pending hashes']))
write('disabled-activation-templates-v1.json',{'schema':'n29-disabled-activation-templates-v1','executable':False,'templates':templates,'contract_path':'experiments/qd_ed_n29/controller-contract-v1.md','note':'None values and outer executable=false are intentional; never copy the wrapper to an authority path. CPU preparation has no release.'})
# Exact test selections are from the saved runner source, not inferred aggregate counts.
runs=[]
for number in range(1,6):
 g=V/f'phase_b_guard_v{number}.py';t=ast.parse(g.read_text());call=next(n for n in ast.walk(t) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='pytest' and n.func.attr=='main')
 runs.append({'run':number,'guard':{'path':str(g),'sha256':sha(g.read_bytes())},'pytest_selection_source':ast.unparse(call),'log':{'path':str(V/f'phase-b-run{number}.log'),'sha256':sha((V/f'phase-b-run{number}.log').read_bytes())},'guard_summary':{'path':str(V/f'phase-b-run{number}-guard.json'),'sha256':sha((V/f'phase-b-run{number}-guard.json').read_bytes())}})
write('phase-b-test-inventory-v1.json',{'schema':'n29-phase-b-test-evidence-v1','phase_b_distinct_cases':73,'phase_a_distinct_cases':38,'phase_b_run_results':[{'run':1,'passed':60,'failed':1,'errors':5,'guard_clean':False},{'run':2,'passed':9,'failed':5,'errors':0,'guard_clean':False},{'run':3,'passed':5,'failed':0,'errors':0,'guard_clean':True},{'run':4,'passed':4,'failed':0,'errors':0,'guard_clean':False,'post_summary_exception':'pytest numbered tmp cleanup dir_fd relative-path guard denial; exit0 and early summary are not whole-process clean evidence'},{'run':5,'passed':4,'failed':0,'errors':0,'guard_clean':True}],'interpretation':'73 distinct Phase B assertion cases eventually pass; only run3 and5 are whole-process guard-clean. Run1/2 passed assertions retain that isolation limitation. No blanket rerun of unaffected passed matrix.','runs':runs})
b=resource.getrusage(resource.RUSAGE_CHILDREN);d=json.loads((V/'phase-b-resource-v1.json').read_text());d['calls'].append({'phase':'final_source_and_template_packaging','children_cpu_seconds':b.ru_utime+b.ru_stime-a.ru_utime-a.ru_stime,'self_cpu_seconds':time.process_time()-start});d['cumulative_n29_cpu_seconds']=d['prior_phase_a_cpu_seconds']+d['preparation_allowance_seconds']+sum(x.get('children_cpu_seconds',0)+x.get('self_cpu_seconds',0) for x in d['calls']);(V/'phase-b-resource-v1.json').write_text(json.dumps(d,indent=2)+'\n')
print(json.dumps({'source_files':len(files),'new_files':len(added),'unchanged_old':len(old)-len(changed),'rdt_unchanged':bridge_summary['rdt_methods_unchanged'],'rdt_total':len(a0),'source':source_ref,'cpu_total':d['cumulative_n29_cpu_seconds']}))
