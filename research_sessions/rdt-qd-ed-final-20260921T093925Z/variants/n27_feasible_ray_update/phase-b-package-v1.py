"""External non-executable handoff assembly; standard-library static metadata only."""
import ast,copy,hashlib,json
from pathlib import Path
V=Path(__file__).resolve().parent;I=V/'implementation';W=V.parent.parent/'study_worktree'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def future(p):return {'path':str(p),'sha256':None}
def write(p,x):
    with Path(p).open('x') as f:json.dump(x,f,indent=2,allow_nan=False);f.write('\n')
constants={}
for n in ast.parse((I/'scripts/qd_ed_n27_contract.py').read_text()).body:
    if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
        try:constants[n.targets[0].id]=ast.literal_eval(n.value)
        except (ValueError,TypeError):pass
source=read(V/'phase-b-source-manifest-v1.json');refs=read(I/'experiments/qd_ed_n27/accepted-predecessor-refs-v1.json')
# Exactly authorized closed frozen-plan metadata; no nested input/proof refs followed.
p=Path(refs['plan']['path']);assert p.stat().st_size<2*1024**2 and sha(p)==refs['plan']['sha256'];old=read(p)
runtime={'path':old['runtime_manifest_path'],'sha256':old['runtime_manifest_sha256']}
protocol=ref(V/'phase-b-integration-protocol-v1.md');arithmetic=ref(V/'independent-arithmetic-protocol-v1.md')
limits=constants['LIMITS'];caps=constants['BASE_CAPS'];cohort=constants['COHORT']
reuse=future(V/'budget-reuse-adoption-v1/authority.json');bridge=future(V/'source-equivalence-bridge-v1.json')
backendproof=future(V/'arithmetic-preflight/proof-v1.json');backend_review=future(V/'arithmetic-preflight-source-review-v1.json')
backend_authority=future(V/'arithmetic-preflight-adoption-v1/authority.json');finalreview=future(V/'final-source-runtime-review-v1.json');authority=future(V/'adoption-v1/authority.json')
resource_limits={'resource_processes':1,'episode_attempts':0,'model_calls':0,'api_calls':0,'simulation_steps':0,'timeout_seconds':120,'cleanup_seconds':40,'physical_gpu':7,'health_gpu_hours_bucket':'recovery'}
def template(name,path,payload):
    write(V/(name+'.disabled-v1.json'),{'schema':'n27-disabled-template-v1','executable':False,'root_adopted':False,
      'output_path':str(path),'unresolved_refs_must_be_bound':True,'payload':payload})
template('budget-reuse-authority',V/'budget-reuse-adoption-v1/authority.json',{'schema':'n27-finite-budget-reuse-v1','existing_budget_authority':refs['budget'],'caps':caps,'protocol':protocol,'predecessor':refs['review'],'local_gpu_hours':9.25,'limits':limits,'recorded_at':None,'authority_interpretation':None,'validation_authorized':False,'formal_authorized':False})
template('source-equivalence-bridge',V/'source-equivalence-bridge-v1.json',{'schema':'n27-source-equivalence-bridge-v1','new_source':source,'runtime':runtime,'predecessor_refs':refs,'root_must_use_exact_bridge_build':True,'gpu_release':False})
template('arithmetic-source-review',V/'arithmetic-preflight-source-review-v1.json',{'schema':'n27-arithmetic-source-review-v1','accepted':True,'source':source,'runtime':runtime,'source_bridge':bridge,'phase_b_protocol':protocol,'arithmetic_protocol':arithmetic,'predecessor':refs['review'],'budget_reuse':reuse,'limits':resource_limits,'gpu_release':False})
template('arithmetic-authority',V/'arithmetic-preflight-adoption-v1/authority.json',{'schema':'n27-arithmetic-resource-authority-v1','source':source,'runtime':runtime,'source_review':backend_review,'budget_reuse':reuse,'limits':resource_limits,'boot_id':None,'automatic_retry':False,'dev_authorized':False,'validation_authorized':False,'formal_authorized':False})
template('arithmetic-release',V/'arithmetic-preflight-release-v1.json',{'schema':'n27-tensor-resource-release-v1','source':source,'runtime':runtime,'authority':backend_authority,'limits':resource_limits,'one_shot':True})
template('final-source-review',V/'final-source-runtime-review-v1.json',{'schema':'n27-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime,'protocol':protocol,'source_plan':refs['plan'],'source_bridge':bridge,'predecessor':refs['review'],'backend_proof':backendproof,'arithmetic_protocol':arithmetic,'budget_reuse':reuse,'no_gpu_release':True})
template('screen-authority',V/'adoption-v1/authority.json',{'schema':'n27-screen-authority-v1','cohort_id':cohort,'source':source,'runtime':runtime,'protocol':protocol,'final_review':finalreview,'budget_reuse':reuse,'limits':limits,'local_gpu_hours':9.25,'recorded_at':None,'authority_interpretation':None,'predecessor':refs['review'],'validation_authorized':False,'formal_authorized':False})
plan=copy.deepcopy(old)
for k in list(plan):
    if k.startswith(('n7_','n9_','n11_','n17_','n18_','n19_','n20_','n21_','n22_','n23_','n24_','n25_','n26_')):plan.pop(k)
rows=[]
for t in range(4):
    for arm,row in zip(constants['ARMS'],old['episodes'][4*t:4*t+4]):
        row=copy.deepcopy(row);row.update(iteration=cohort,profile=arm,episode_key=f'n27_screen_t{t:02d}_{arm.lower()}_20261001');rows.append(row)
plan.update(frozen=False,worktree=str(W),source_commit=source['commit'],code_files=source['files'],episodes=rows,
 candidate_profiles={a:{'path':str(W/f'configs/qd_ed_final/candidate_{a.lower()}.json'),'sha256':sha(I/f'configs/qd_ed_final/candidate_{a.lower()}.json')} for a in ('N26','N27')},
 phase_authorization={'dev':True,'validation':False,'formal':False},derived_from=refs['plan'])
plan['scientific_config_files']=sorted(set(plan['scientific_config_files'])|{'configs/qd_ed_final/candidate_n26.json','configs/qd_ed_final/candidate_n27.json'})
plan['n27_cohort']={'schema':'n27-feasible-ray-screen-v1','cohort_id':cohort,'limits':limits,'protocol':protocol,'source_plan':refs['plan'],
 'timeout_observability':{'path':str(V.parent/'n23_actuator_clipped_quality/timeout-observability-addendum-v2.md'),'sha256':constants['OBSERVABILITY_SHA']},
 'final_review':None,'authority':None,'predecessor':refs['review'],'budget_reuse':None,'worker_audit':constants['WORKER_CONTRACT'] if 'WORKER_CONTRACT' in constants else {'schema':'n27-same-process-native-audit-v1','arms':list(constants['ARMS']),'cuda_arithmetic_arms':['N26','N27'],'other_arm_backend':'cpu','timeout_includes_audit':True,'profile_bound_rbf_audit':True,'witness_exact_backend':'assigned_cuda'},
 'n26_role':'control_only_no_promotion','early_stop':'none_full_sixteen_required'}
write(V/'plan.draft.disabled-v1.json',plan)
template('screen-release',V/'execution-release-v1.json',{'schema':'n27-dev-execution-release-v1','plan':future(V/'plan.frozen.v1.gpu7.json'),'source_commit':source['commit'],'cohort_id':cohort,'episode_keys':[r['episode_key'] for r in rows],'authority':authority,'physical_gpu':7,'limits':limits,'validation_authorized':False,'formal_authorized':False})
print(json.dumps({'templates':8,'draft_rows':len(rows),'frozen':False,'source_files':len(source['files'])}))
