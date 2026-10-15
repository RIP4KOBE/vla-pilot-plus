import json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE/'implementation';sys.path.insert(0,str(ROOT))
from scripts import qd_ed_n25_contract as c,qd_ed_n25_backend as b,qd_ed_final_runner as r
OUT=HERE/'phase-b-templates-v1';OUT.mkdir(exist_ok=False)

def save(name,target,payload,missing):
    value={'schema':'n25-disabled-preparation-template-v1','executable':False,'authorization':False,
        'target_path':str(target),'missing_prerequisites':missing,'payload':payload}
    (OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

save('predecessor-review.template.json',c.PREDECESSOR,{'schema':'n25-predecessor-review-v1',
 'source_commit':'3b7afa02757eb3519d95547e4b6e6e939f7068f2','dev_result':None,'dev_root_review':None,
 'disposition':'VALID_DEV_REJECTION','validation_review':None,'allow_n25':False},['root fills and verifies original aggregate references, then explicitly allows successor'])
save('budget-authority.template.json',c.BUDGET_AUTHORITY,{'schema':'n25-finite-budget-authority-v1','cohort_id':c.COHORT,
 'caps':None,'amendment':None,'amendment_document':None,'predecessor':None,'recorded_at':None,'authority_interpretation':None},
 ['root adopts exact finite attempts/buckets under private locks; preparation keeps478/100 unchanged','100h,validation180/formal40/recovery20,protected32/12 immutable here'])
save('arithmetic-source-review.template.json',b.REVIEW,{'schema':'n25-arithmetic-source-review-v1','accepted':False,
 'source':None,'runtime':None,'source_bridge':None,'phase_b_protocol':None,'arithmetic_protocol':None,
 'predecessor':None,'budget_authority':None,'limits':b.LIMITS,'gpu_release':False},['root final committed source/runtime review'])
save('arithmetic-authority.template.json',b.AUTHORITY,{'schema':'n25-arithmetic-resource-authority-v1','source':None,'runtime':None,
 'source_review':None,'budget_authority':None,'limits':b.LIMITS,'boot_id':None,'automatic_retry':False,
 'dev_authorized':False,'validation_authorized':False,'formal_authorized':False},['root adopts exact resource authority in state.n25_arithmetic_authority'])
save('arithmetic-release.template.json',b.RELEASE,{'schema':'n25-tensor-resource-release-v1','source':None,'runtime':None,
 'authority':None,'limits':b.LIMITS,'one_shot':True},['root current GPU7 admission and one-shot release; no proof exists yet'])
save('arithmetic-plan.template.json',b.PLAN,{'schema':'n25-tensor-resource-plan-v1','frozen':False,'resource_id':None,
 'kind':b.KIND,'worktree':None,'source':None,'runtime':None,'limits':b.LIMITS,'authority':None,
 'output_dir':str(c.RUN_DIR/'arithmetic-preflight/worker')},['only admitted backend.run freezes resource plan before charging one worker'])
save('final-source-runtime-review.template.json',c.FINAL_REVIEW,{'schema':'n25-source-runtime-review-v1','disposition':'NOT_REVIEWED',
 'source':None,'runtime':None,'protocol':None,'source_plan':None,'source_bridge':None,'predecessor':None,
 'backend_proof':None,'arithmetic_protocol':None,'no_gpu_release':True},['actual successful, fully metered tensor proof; exact same final source for future Dev'])
save('dev-authority.template.json',c.AUTHORITY,{'schema':'n25-dev-authority-v1','cohort_id':c.COHORT,'source':None,'runtime':None,
 'protocol':None,'final_review':None,'budget_authority':None,'limits':c.LIMITS,'local_gpu_hours':None,
 'recorded_at':None,'authority_interpretation':None,'validation_authorized':False,'formal_authorized':False},
 ['root finite local hours after actual preflight accounting','root state.n25_dev_authority adoption'])
save('dev-release.template.json',c.RUN_DIR/'execution-release-v1.json',{'schema':'n25-dev-execution-release-v1','plan':None,
 'source_commit':None,'cohort_id':c.COHORT,'episode_keys':None,'authority':None,'physical_gpu':7,'limits':c.LIMITS,
 'validation_authorized':False,'formal_authorized':False},['root exact frozen40cell plan/source/budget/resource review'])
save('dev-plan.template.json',c.RUN_DIR/'plan.frozen.v1.gpu7.json',{'frozen':False,'source_commit':None,'code_files':None,
 'runtime_manifest_path':None,'runtime_manifest_sha256':None,'episodes':None,'phase_authorization':{'dev':False,'validation':False,'formal':False},
 'n25_cohort':{'cohort_id':c.COHORT,'limits':c.LIMITS,'authority':None,'final_review':None}},
 ['actual original frozen Dev identity metadata derivation by prepare.build_plan','all root gates plus actual same-source CUDA proof'])
(HERE/'source-paths-controller-v1.json').write_text(json.dumps(sorted(c.source_paths(vars(r))),indent=2)+'\n')
print(json.dumps({'templates':10,'all_executable':False,'source_paths':len(c.source_paths(vars(r))),'gpu_dispatched':False}))
