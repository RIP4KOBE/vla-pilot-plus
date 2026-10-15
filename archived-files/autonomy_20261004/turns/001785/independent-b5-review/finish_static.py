from pathlib import Path
O=Path(__file__).parent
exec((O/'inspect_static.py').read_text().split("print('INDEX_KEYS'")[0])
check('all40_index_binding',IX['audit']==G['audit'] and IX['release_enabled'] is False and len(IX['manifests'])==len(AU['episodes'])==len(AU['expected_manifests'])==40)
keys=[]
for item in IX['manifests']:
 row=item['row'];key=row['episode_key'];keys.append(key);m=read(item['new'])
 check('index_row_'+key,AU['expected_manifests'][key]==item['new'] and row in AU['episodes'] and m['row']==row)
 check('manifest_bindings_'+key,all(m[k]==G[k] for k in ['runtime','runtime_closure','native_build','controller_semantics']) and m['source']==P['source'])
check('all40_unique_matrix',len(set(keys))==40 and {(x['task_id'],x['profile']) for x in AU['episodes']}=={(t,a) for t in range(10) for a in ['C0','Q0','N34','N36']})
check('separate_engineering_manifest',EN['row']['episode_key'] not in keys and P['expected_manifests']=={EN['row']['episode_key']:G['separate_engineering_manifest']} and EN['audit_plan']==G['audit'] and EN['audit_manifest']==AU['expected_manifests'][EN['audit_row']['episode_key']] and EN['row']==S['scope']['episode'] and all(EN[k] is False for k in ['scientific_eligible','promotion_eligible','matched_improvement_eligible']))
check('audit_disabled',AU['release_enabled'] is False and AU['phase_authorization']==dict(dev=False,validation=False,formal=False))
recon=read(RP['root_terminal_reconciliation']);review=read(RP['accepted_review'])
check('recovery_accepted_unchanged',recon['root_accepts_blocking_findings'] is True and recon['live_handles']==[] and {k:recon['review'][k] for k in ['path','sha256']}==RP['accepted_review'] and recon['ledger_prefixes']==RP['root_observed_ledger_prefixes'])
check('successor_unused',all(G['resource_id'].encode() not in pathlib.Path(ref['path']).read_bytes() for ref in A['ledger_prefixes'].values()))
check('canonical_runtime_paths',all(str(pathlib.Path(G[k]['path']).resolve())==G[k]['path'] for k in ['runtime','source_record','runtime_closure']))
oldct=read(CT['historical_review']);oldrt=read(oldct['runtime']);oldcl=read(oldct['runtime_closure'])
print('ACTUAL_RUNTIME_DELTA',diff(oldrt,R)); print('ACTUAL_CLOSURE_DELTA',diff(oldcl,CL))
check('accepted_runtime_delta',set(diff(oldrt,R)) <= {'.preparation.source_record.path','.preparation.source_record.sha256'} and read(oldrt['preparation']['source_record'])==V['source_record'])
check('accepted_closure_delta',diff(oldcl,CL)==['.runtime.path','.runtime.sha256'])
sourcefiles={x['path']:x['sha256'] for x in P['source']['files']}
source_paths=['scripts/qd_ed_n36_engineering_r1.py','scripts/qd_ed_n36_readiness_prepare.py','scripts/qd_ed_n34_controller.py','scripts/qd_ed_n36_stop.py']
for path in source_paths:
 b=pathlib.Path(path).read_bytes();check('reviewed_consumer_source_'+path,digest(b)==sourcefiles[path]);inputs[str(pathlib.Path(path).resolve())]={'path':str(pathlib.Path(path).resolve()),'sha256':digest(b),'bytes':len(b)}
# Evaluate only the exact pure static consumer function; no module imports or deployment execution.
import types,math
module=ast.parse(pathlib.Path('scripts/qd_ed_n34_controller.py').read_text())
fn=next(x for x in module.body if isinstance(x,ast.FunctionDef) and x.name=='verify_semantics')
fields=ast.literal_eval(next(x for x in module.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FIELDS' for t in x.targets)).value)
def require(ok,label):
 if not ok:raise ValueError(label)
ns={'w':types.SimpleNamespace(read_ref=read,require=require),'math':math,'FIELDS':fields}
exec(compile(ast.Module(body=[fn],type_ignores=[]),'exact-source-verify_semantics','exec'),ns)
ns['verify_semantics'](G['controller_semantics'],G['runtime'],CL)
check('exact_static_controller_function',True,'AST-extracted unchanged production function; dependencies limited to JSON hash reads and math; no simulator import')
stop_paths=list(dict.fromkeys(A['stop_authority']['paths']+P['stop_authority']['paths']))
stop=[{'path':p,'present':pathlib.Path(p).exists() or pathlib.Path(p).is_symlink()} for p in stop_paths]
check('STOP_and_deadline',not any(x['present'] for x in stop) and datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(A['stop_authority']['deadline'].replace('Z','+00:00')),stop)
check('retained_original_prefix_contract',RP['original_ledger_prefixes']==S['retained_ledger_prefixes'] and RP['identity']==S['readiness_recovery'])
# Final byte comparisons avoid claiming a lock or live accounting adoption.
for ref in A['ledger_prefixes'].values():
 b=pathlib.Path(ref['path']).read_bytes();check('final_ledger_'+pathlib.Path(ref['path']).name,len(b)==ref['bytes'] and digest(b)==ref['sha256'])
(O/'inspection-results-v1.json').write_text(json.dumps({'inputs':list(inputs.values()),'checks':checks,'ledger_checks':ledger_checks,'replacement_diffs':replacement_diffs,'stop_observation':stop},indent=2)+'\n')
print('PASS',len(checks),'checks;',len(inputs),'hash-bound input files')
