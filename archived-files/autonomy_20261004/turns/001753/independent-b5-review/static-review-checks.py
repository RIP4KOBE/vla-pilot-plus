import ast,copy,datetime as dt,hashlib,json,os,pathlib,subprocess
O=pathlib.Path(__file__).parent
E={}; checks=[]
def raw(p):
 p=pathlib.Path(p);s=str(p).lower()
 assert not any(x in s for x in ['2026-08-10','credentials','auth.json','/protected-results/','/validation/results/','/formal/results/','poe']),s
 b=p.read_bytes();E[str(p)]={'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()};return b
def read(r):
 b=raw(r['path']);assert hashlib.sha256(b).hexdigest()==r['sha256'],r['path']
 if 'bytes' in r:assert len(b)==r['bytes'],r['path']
 return json.loads(b)
def record(p):raw(p);return E[str(p)]
def ck(label,fn):
 fn();checks.append({'check':label,'status':'PASS'})
def eq(x,y):assert x==y,(str(x)[:200],str(y)[:200])
def yes(x):assert x
A=json.loads(raw(O/'authority-v1.json'));G=read(A['graph']);I=read(A['final_index']);R=read(A['report']);ROOT=pathlib.Path(A['source']['worktree']);B=pathlib.Path(A['graph']['path']).parent
D={k:read(v) for k,v in G.items() if isinstance(v,dict) and 'path' in v and 'sha256' in v}
P=D['plan'];AU=D['audit'];S=D['specification'];C=D['recovery_prefix_contract'];POL=D['policy'];RM=D['relocation_map'];SR=D['source_record'];RT=D['runtime'];CL=D['runtime_closure'];CTRL=D['controller_semantics'];ACC=D['root_controller_acceptance'];F=D['full40_manifests'];EM=D['separate_engineering_manifest']
for k in ['scope','accounting','deployment']:D[k]=read(P[k])
ck('Authority graph/index/report cross-bindings',lambda:[eq(I['graph'],A['graph']),eq(R['graph'],A['graph']),eq(I['final_report'],A['report']),eq(G['root_controller_acceptance']['sha256'],A['root_controller_acceptance']['sha256'])])
CE=read(R['command_evidence']);receipt=read(I['command_receipts'][-1]);rawlog=raw(receipt['stdout_stderr']['path']);eq(E[receipt['stdout_stderr']['path']],receipt['stdout_stderr']);builder=raw(receipt['builder']['path']);eq(E[receipt['builder']['path']],receipt['builder'])
GM=read(R['generated_artifact_manifest']);read(I['generated_artifact_manifest']);read(R['input_manifest']);sb=raw(I['final_report_sha256']['path']);eq(E[I['final_report_sha256']['path']],I['final_report_sha256']);yes(sb.decode().startswith(A['report']['sha256']));
VI=read(next(x for x in GM['files'] if x['path'].endswith('/disabled-graph-validator-input-v1.json')))
ck('Reused exact production all41 command evidence',lambda:[eq(receipt['process_exit_code'],0),eq(receipt['report'],A['report']),eq(CE['checks'],R['checks']),yes(all(x['status']=='PASS' for x in CE['checks'])),eq(CE['builder_counts'],{'audit':40,'engineering':1}),eq(VI,{'graph':{'plan':G['plan'],'runtime':G['runtime']},'release_enabled':False,'approved':False}),eq(CE['validator_bypass'],False),eq(CE['production_sources_unmodified'],True),eq(CE['model_loading_inference_native_build_provider_gpu_invocations'],0),yes(b'prep.verify_graph(read(validator_input),source,baseline)' in builder),yes(b'PASS production complete disabled graph verify_graph all41' in rawlog)])
def git(*args):return subprocess.check_output(['git','--no-replace-objects','-C',str(ROOT),*args],text=True).strip()
ck('Current committed source/tree and tracked cleanliness',lambda:[eq(git('rev-parse','HEAD'),A['source']['commit']),eq(git('rev-parse','HEAD^{tree}'),A['source']['tree']),eq(git('status','--porcelain','--untracked-files=no'),''),eq(SR,P['source']),eq(SR,P['scientific_source'])])
sourcepath=ROOT/'scripts/qd_ed_n36_engineering_r1.py';sourcebytes=raw(sourcepath);tree=ast.parse(sourcebytes)
const={}
for n in tree.body:
 if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
  try:const[n.targets[0].id]=ast.literal_eval(n.value)
  except (ValueError,TypeError):
   if n.targets[0].id=='OPERATIONAL_FILES':const['OPERATIONAL_FILES']=set(ast.literal_eval(n.value.args[0]))
for name in ['qd_ed_n36_engineering_r1.py','qd_ed_n36_readiness_prepare.py','qd_ed_n36_contract.py','qd_ed_n36_stop.py','qd_ed_n36_accounting.py','qd_ed_n34_controller.py']:
 p=ROOT/'scripts'/name;raw(p);entry=next(x for x in SR['files'] if x['path']=='scripts/'+name);eq(E[str(p)]['sha256'],entry['sha256'])
EQ=D['scientific_equivalence'];changes=sorted(git('diff','--name-only',EQ['base_commit'],SR['commit'],'--').splitlines())
ck('Frozen scientific source equivalence',lambda:[eq(EQ['source'],SR),eq(EQ['base_commit'],const['BASE']),eq(changes,EQ['changed_paths']),yes(set(changes)<=const['OPERATIONAL_FILES']),eq(EQ['scientific_changes'],False),eq(subprocess.run(['git','--no-replace-objects','merge-base','--is-ancestor',const['BASE'],SR['commit']],cwd=ROOT).returncode,0)])
ck('Disabled graph/plan and audit-only frozen snapshot',lambda:[yes(all(G[k] is False for k in ['release_enabled','frozen','runtime_ready','provider_ready','gpu_authorized','provider_measurement_authorized'])),yes(all(G[k] is None for k in ['authority','b5_review','root_acceptance'])),yes(P['release_enabled'] is P['frozen'] is False),yes(P['authority'] is P['b5_review'] is None),yes(all(v is False for v in P['phase_authorization'].values())),yes(AU['frozen'] is True and AU['release_enabled'] is AU['dispatch_authority'] is False),yes(all(v is False for v in AU['phase_authorization'].values())),eq(P['limits'],const['LIMITS'])])
# Original immutable plan is a bounded scientific contract reference, not results.
OR=read(S['full_audit_view']['immutable_original_plan'])
ck('All40 frozen scientific matrix and rules',lambda:[eq(AU['episodes'],OR['episodes']),eq(len(AU['episodes']),40),eq([(x['task_id'],x['profile']) for x in AU['episodes']],[(t,a) for t in range(10) for a in ['C0','Q0','N34','N36']]),*[eq(AU[k],OR[k]) for k in ['limits','worker_contract','deadline','protocol','protocol_review','accounting']]])
ck('All40 index and separate engineering manifest bindings',lambda:[eq(F['audit'],G['audit']),eq(len(F['manifests']),40),eq([x['row'] for x in F['manifests']],AU['episodes']),eq({x['row']['episode_key']:x['new'] for x in F['manifests']},AU['expected_manifests']),eq(EM['row'],P['episodes'][0]),eq(EM['audit_row'],AU['episodes'][0]),eq(EM['audit_manifest'],F['manifests'][0]['new']),eq(P['engineering_manifest'],G['separate_engineering_manifest']),eq(EM['audit_plan'],G['audit']),yes(all(EM[k] is False for k in ['scientific_eligible','promotion_eligible','matched_improvement_eligible']))])
for x in F['manifests']:
 m=read(x['new']);eq(m['row'],x['row']);eq(m['dispatch_authority'],False)
 for k in ['source','scientific_source','runtime','runtime_closure','controller_semantics','native_build','scope','deployment']:eq(m[k],P[k])
for k in ['source','scientific_source','runtime','runtime_closure','controller_semantics','native_build','scope','deployment']:eq(EM[k],P[k])
checks.append({'check':'40 manifest byte hashes and per-row/common bindings; engineering manifest remains distinct','status':'PASS'})
BASE=read(S['canonical_runtime']);projected=copy.deepcopy(BASE);projected['preparation']['source']=SR['commit'];projected['preparation']['source_record']=G['source_record']
ck('Exact disabled runtime projection and closure/controller consistency',lambda:[eq(RT,projected),eq(CL['runtime'],G['runtime']),eq(CTRL['runtime'],G['runtime']),eq(CTRL['runtime_closure'],G['runtime_closure']),eq(CTRL['source_commit'],SR['commit']),eq(CTRL['status'],'ROOT_REVIEWED'),eq(ACC['controller']['sha256'],G['controller_semantics']['sha256']),eq(ACC['runtime'],G['runtime']),eq(ACC['runtime_closure'],G['runtime_closure']),yes(RT['provider_ready'] is RT['cuda_egl_verified'] is RT['preparation']['runtime_ready'] is False),eq(POL['disabled_runtime_path'],G['runtime']['path'])])
ledger={k:raw(v['path']) for k,v in A['ledger_prefixes'].items()}
for k,v in A['ledger_prefixes'].items():eq(len(ledger[k]),v['bytes']);eq(hashlib.sha256(ledger[k]).hexdigest(),v['sha256']);yes(ledger[k].endswith(b'\n'))
for anchors in [S['retained_ledger_prefixes'],C['original_ledger_prefixes'],C['root_observed_ledger_prefixes']]:
 for k,v in anchors.items():eq(hashlib.sha256(ledger[k][:v['bytes']]).hexdigest(),v['sha256'])
pred=C['predecessor'];retained=raw(pred['raw_sequence']['path']);eq(hashlib.sha256(retained).hexdigest(),pred['raw_sequence']['sha256']);eq(ledger['readiness-preparation-ledger.jsonl'],retained);eq(ledger['gpu-healthcheck-ledger.jsonl'][114767:119910],retained);eq(len(retained),5143)
rows=[json.loads(x) for x in retained.splitlines()];eq(rows,pred['rows']);eq([x['event'] for x in rows],['reserved','dispatched','aborted'])
for line,seg in zip(retained.splitlines(keepends=True),pred['row_segments']):eq(len(line),seg['bytes']);eq(hashlib.sha256(line).hexdigest(),seg['sha256']);eq(ledger['gpu-healthcheck-ledger.jsonl'][seg['global_start_inclusive']:seg['global_end_exclusive']],line)
for b in ledger.values():yes(G['resource_id'].encode() not in b)
ID=read(C['identity']);reconciliation=read(C['root_terminal_reconciliation']);read(C['accepted_review'])
ck('Current complete ledger prefixes and raw predecessor/recovery identity contract',lambda:[eq(S['retained_ledger_prefixes'],C['original_ledger_prefixes']),eq(POL['resource_id'],G['resource_id']),eq(C['successor']['resource_id'],G['resource_id']),eq(ID['resource_id'],G['resource_id']),eq(ID['recovery_of'],G['recovery_of']),eq(pred['resource_id'],G['recovery_of']),eq(pred['retained_charge_gpu_hours'],0.045194898711310494),eq(rows[-1]['gpu_process_wall_seconds']/3600,0.045194898711310494),eq(rows[-1]['telemetry_complete'],False),eq(rows[-1]['provider_calls'],1),eq(reconciliation['live_handles'],[]),eq(reconciliation['root_accepts_blocking_findings'],True)])
ck('Frozen accounting/reserves, separate future finite preparation budget',lambda:[eq(D['accounting']['accounting'],S['accounting_proposal']),eq(D['accounting']['retained_ledger_prefixes'],S['retained_ledger_prefixes']),eq(D['accounting']['root_adopted'],False),eq(S['accounting_proposal']['absolute_cap_gpu_hours'],'224'),eq(S['accounting_proposal']['effective_weekly_cap_gpu_hours'],'221.08404692669838'),eq(S['accounting_proposal']['retained_admission_margin_gpu_hours'],'0.23357169027962'),eq(S['accounting_proposal']['protected_remaining_gpu_hours'],{'formal':'12.0','validation':'24.2408240024308155'}),eq(S['accounting_proposal']['retained_attempts'],507),eq(S['accounting_proposal']['gpu_reservation_seconds'],1900),eq(S['accounting_proposal']['wall_seconds'],2100),yes(C['full_ledgers_required_for_budget_snapshots'] is True)])
slots=read(RM['original_slots']);eq(RM['original_specification_content'],S);eq(RM['original_slot_content'],slots)
mapkeys={'audit_view':G['audit'],'engineering_plan':G['plan'],'engineering_manifest':G['separate_engineering_manifest'],'full40_manifest_index':G['full40_manifests'],'native_build':G['native_build'],'scope':P['scope'],'accounting':P['accounting'],'deployment':P['deployment'],'scientific_equivalence':G['scientific_equivalence'],'controller_semantics':G['controller_semantics']}
for k,v in mapkeys.items():eq(RM['relocations'][k],{'original':slots['slots'][k],'new':v})
for i,x in enumerate(F['manifests']):eq(x['original'],slots['full40_manifests'][i])
ck('Exact relocation bindings without adopting prospective slots',lambda:[eq(RM['full40'],F['manifests']),eq(RM['release_enabled'],False),eq(RM['adoption_authorized'],False),eq(RM['active_specification_changed'],False),eq(I['graph_slot_relocation']['new'],A['graph']),eq(I['graph_slot_relocation']['original'],slots['slots']['graph'])])
stopobs=[{'path':p,'lexists':os.path.lexists(p)} for p in A['stop_authority']['paths']]
ck('Canonical STOP/deadline consistency; no dispatch authority',lambda:[eq(P['stop_authority'],A['stop_authority']),eq(AU['stop_authority'],A['stop_authority']),eq(D['deployment']['stop_authority'],A['stop_authority']),eq(P['deadline'],A['stop_authority']['deadline']),eq(dt.datetime.fromisoformat(POL['deadline']),dt.datetime.fromisoformat(P['deadline'].replace('Z','+00:00')))])
for k,v in A['ledger_prefixes'].items():eq(raw(v['path']),ledger[k])
eq(git('status','--porcelain','--untracked-files=no'),'')
result={'checks':checks,'verified_files':list(E.values()),'stop_observations':stopobs,'source':A['source'],'review_bindings':{k:P[k] for k in const['BINDINGS']},'composition_command_evidence':R['command_evidence'],'composition_invocation':CE['invocation'],'full_all41_rerun':False,'at':dt.datetime.now(dt.timezone.utc).isoformat()}
(O/'static-check-results-v1.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps({'checks':checks,'verified_file_count':len(E),'stop':stopobs},indent=2))
