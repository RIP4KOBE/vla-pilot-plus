import sys,json,hashlib,os
from pathlib import Path
import yaml
root=Path.cwd();sys.path.insert(0,str(root))
from scripts import qd_ed_final_runner as r
out=root.parent/'autonomy_20261004/turns/000849';record=json.loads((out/'terminal-reconciliation-v1.json').read_text());ref={'path':str((out/'terminal-reconciliation-v1.json').resolve()),'sha256':r.digest(out/'terminal-reconciliation-v1.json')}
for item in record['receipt_checks']: assert item['audit_summary']['accepted'] is True
statepath=root/'research-state.yaml';cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(root/'data/qd-ed-state.lock'):
  for name,x in record['ledger_prefixes'].items():
   p=root/'data'/name;assert p.stat().st_size==x['bytes'] and r.digest(p)==x['sha256']
  assert not Path('/proc/1322966').exists()
  s=r.read_state(statepath);c=json.loads(cp.read_text());assert s['active_controller']==c['active_controller']==record['controller']
  (out/'research-state.before.yaml').write_bytes(statepath.read_bytes());(out/'checkpoint.before.json').write_bytes(cp.read_bytes())
  for obj in (s,c):
   obj['active_controller']={**obj['active_controller'],'terminal_status':'BUDGET_CAPPED_PARTIAL_COHORT_NO_PROMOTION','terminal_reconciliation':ref,'live_handles':[]}
   obj['n34r11_terminal_reconciliation']=ref
   obj['status']='N34R11_BUDGET_CAPPED_PARTIAL_COHORT'
   obj['phase']='DEV_TERMINAL_RECONCILED_PROSPECTIVE_REVIEW'
   obj['next_action']=record['next_bounded_step']
   obj['automatic_gpu_dispatch_authorized']=False
   obj['automatic_gpu_dispatch_scope']='No active release: N34R11 stopped at immutable cohort admission ceiling; separate prospective release required.'
   obj['budget_snapshot']=record['budget_snapshot']
  for path,data in [(statepath,yaml.safe_dump(s,sort_keys=False)),(cp,json.dumps(c,indent=2)+'\n')]:
   tmp=path.with_name(path.name+'.turn849-tmp')
   with tmp.open('w') as f:f.write(data);f.flush();os.fsync(f.fileno())
   os.replace(tmp,path)
  (out/'state-adoption-v1.json').write_text(json.dumps({'schema':'n34r11-terminal-state-adoption-v1','reconciliation':ref,'state_after_sha256':r.digest(statepath),'checkpoint_after_sha256':r.digest(cp),'source_unchanged':record['source'],'ledger_prefixes':record['ledger_prefixes'],'budget_caps_unchanged':True,'history_preserved':True,'no_dispatch':True},indent=2)+'\n')
summary=f'''Turn849 operational summary

Source {record['source']}; scientific source 1065f38122379a515b60a9a424f574330405b66f unchanged. Driver PID268073/start97715947 remains owner; controller PID1322966/start137471973 is absent, all19 worker handles settled. Prior turn848 exited normally; controller stopped afterward at 2026-10-09T08:19:31Z with cohort_seconds_remaining insufficient. No STOP; authorization ends2026-10-11T11:13:13Z.

Reconciled19 valid terminals, receipt and native audit report hashes/acceptance and all three prior ledger prefixes. No replay of full native audits. Cumulative472 dispatches/69.38354303190809GPUh. R11 consumed4.56916299913887GPUh, leaving1551.0132031000685s of18000s, below1840s admission by288.9867968999315s. No invalid/new reservation from this refusal. All old charges, unknown telemetry, reserves and ledgers preserved.

Scientific disposition: budget-capped partial cohort, no promotion. Six complete triples C0=0/6,Q0=0/6,N34=1/6. Task6 C0 valid failure excluded from matched denominators; task6 Q0/N34 and tasks7-9 unobserved. Upper bound1+4=5 is not numerical futility. Frozen30-valid-cell and>=5/10 gates not passed. Validation/formal/ablation evidence unresolved; goal_complete=false.

Updated owning state/checkpoint under normal operation locks with hash-bound terminal reconciliation; archived both preimages. Retained historical controller identity and marked terminal/no live handles. Closed this exhausted release's automatic-dispatch flag only; standing authorization remains valid. No driver lease acquisition, dispatch, source/plan/scientific-threshold edit or foreign write.

Next bounded step: {record['next_bounded_step']} Budget approval is already supplied. Document exact finite arithmetic before adoption; use isolated executor worktree if implementation is needed. Existing cohort freeze stays intact. Prospective statistical interpretation of partial-prefix evidence must be explicit, never silently pooled or portrayed as complete.
'''
(out/'operational-summary.md').write_text(summary)
print('Terminal reconciliation adopted; summary written.')
