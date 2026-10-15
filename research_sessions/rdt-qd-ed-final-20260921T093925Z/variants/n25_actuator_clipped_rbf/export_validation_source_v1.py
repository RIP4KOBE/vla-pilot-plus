"""Export static committed sources and disabled templates; no live evidence access."""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE/'validation_implementation'
sys.path.insert(0,str(ROOT))
import n25_validation_source_guard_v1
import ast,hashlib,json,subprocess
from scripts import qd_ed_n25_validation_bridge as bridge
from scripts import qd_ed_n25_validation_contract as c
from scripts import qd_ed_n23_worker as w
old=json.loads((HERE/'source-manifest-controller-v1.json').read_text())
assert w.sha(HERE/'source-manifest-controller-v1.json')=='fafcb0d881c95d567cb14a6690145d4ad933abc84a5e0175dfbe1512efd836ee'
parent={'source_commit':old['commit'],'code_files':old['files']}
source,record=bridge.source_record(ROOT,parent,c.PROTOCOL_SHA,c.ROUTING_SHA)
assert len(source['files'])==270
assert subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)==''
w.atomic_json(HERE/'validation-source-manifest-v1.json',source)
w.atomic_json(HERE/'validation-source-bridge-v1.json',record)
def ref(p):return {'path':str(p.resolve()),'sha256':w.sha(p)}
comparison=[]
for path in sorted(bridge.MODIFIED):
    before=bridge.original(ROOT,path).decode();after=(ROOT/path).read_text()
    def bodies(text):return {n.name:ast.get_source_segment(text,n) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
    a,b=bodies(before),bodies(after)
    same=[k for k in a if a[k]==b.get(k)]
    changed=[k for k in a if a[k]!=b.get(k)]
    if path.endswith('qd_ed_n23_worker.py'):assert changed==['validate_context'] and set(a)==set(b)
    comparison.append({'path':path,'old_sha256':hashlib.sha256(before.encode()).hexdigest(),
        'new_sha256':hashlib.sha256(after.encode()).hexdigest(),'original_functions':len(a),
        'unchanged_functions':same,'changed_functions':changed,'new_functions':sorted(set(b)-set(a))})
w.atomic_json(HERE/'validation-function-bridge-v1.json',{'schema':'n25-validation-function-bridge-v1',
    'base':bridge.DEV_COMMIT,'commit':source['commit'],'original_files':257,'unchanged_original_files':255,
    'reverse_verified':True,'files':comparison,'source_manifest':ref(HERE/'validation-source-manifest-v1.json')})
diff=subprocess.check_output(['git','diff','--binary',bridge.DEV_COMMIT,'HEAD'],cwd=ROOT)
with (HERE/'validation-source-diff-v1.patch').open('xb') as f:f.write(diff)
templates=HERE/'validation-cpu-templates-v1';templates.mkdir(exist_ok=False)
common={'schema':'n25-disabled-validation-template-v1','executable':False,'protected_execution_authorized':False,
    'validation_authorized':False,'formal_authorized':False,'source_manifest':ref(HERE/'validation-source-manifest-v1.json'),
    'source_bridge':ref(HERE/'validation-source-bridge-v1.json'),
    'missing_prerequisites':['actual complete Dev promotion','root terminal/source review','integration after Dev',
      'current fresh metadata','actual full capacity','specific adopted authority','exact frozen plan and release']}
runtime={'path':None,'sha256':None}
devreview={'schema':'n25-dev-promotion-review-v1','disposition':'UNREVIEWED','dev_plan':{'path':str(c.DEV_PLAN),'sha256':c.DEV_PLAN_SHA},
    'dev_status':{'path':str(c.DEV_STATUS),'sha256':None},'dev_result':{'path':str(c.DEV_RESULT),'sha256':None},
    'dev_source_bridge':{'path':str(c.dev.BRIDGE),'sha256':None},'allow_validation':False}
srcreview={'schema':'n25-validation-source-review-v1','disposition':'UNREVIEWED','dev_plan':devreview['dev_plan'],
    'protocol':ref(c.PROTOCOL),'routing_addendum':ref(c.ROUTING_ADDENDUM),'source':source,'source_bridge':record,
    'runtime':runtime,'dev_source_bridge':devreview['dev_source_bridge'],'no_execution_release':True}
authority={'schema':'n25-validation-authority-v1','cohort_id':c.COHORT,'seed_cohort':None,'source':source,
    'dev_review':{'path':str(c.DEV_REVIEW),'sha256':None},'source_review':{'path':str(c.SOURCE_REVIEW),'sha256':None},
    'protocol':ref(c.PROTOCOL),'routing_addendum':ref(c.ROUTING_ADDENDUM),'runtime':runtime,'limits':c.LIMITS,'caps':c.CAPS,
    'recorded_at':None,'authority_interpretation':None,'validation_authorized':False,'formal_authorized':False}
release={'schema':'n25-validation-execution-release-v1','plan':{'path':str(c.VALIDATION_PLAN),'sha256':None},
    'source_commit':source['commit'],'cohort_id':c.COHORT,'seed_cohort':None,'episode_keys':None,'limits':c.LIMITS,
    'dev_review':authority['dev_review'],'source_review':authority['source_review'],
    'authority':{'path':str(c.AUTHORITY),'sha256':None},'physical_gpu':7,'uuid':c.GPU7_UUID,
    'validation_authorized':False,'formal_authorized':False}
draft={'schema':'n25-disabled-plan-outline-v1','frozen':False,'source_commit':source['commit'],'code_files':source['files'],
    'matrix':{'order':['block b1,b2','task 0..9','C0,Q0,N25'],'primary_cells':60,'seed_cohort':None},
    'attempt_artifact_root':'inherit exact future admitted Dev runtime','controller_output':str(c.RUN_DIR/'validation-execution'),
    'runtime':runtime,'authority':None,'dev_review':None,'no_new_gpu_preflight':True}
for name,value in [('dev-review',devreview),('source-review',srcreview),('authority',authority),('release',release),('plan-outline',draft)]:
    w.atomic_json(templates/(name+'.disabled.json'),{**common,'record':value})
w.atomic_json(templates/'manifest.json',{'schema':'n25-disabled-template-index-v1','executable':False,
    'files':[ref(p) for p in sorted(templates.glob('*.disabled.json'))]})
print(json.dumps({'commit':source['commit'],'files':len(source['files']),'source_manifest':ref(HERE/'validation-source-manifest-v1.json'),
    'source_bridge':ref(HERE/'validation-source-bridge-v1.json'),'template_index':ref(templates/'manifest.json'),
    'real_evidence_reads':0,'dispatches':0}))
