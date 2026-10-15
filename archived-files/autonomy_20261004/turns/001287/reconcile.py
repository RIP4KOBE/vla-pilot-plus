import pathlib,json,hashlib,datetime,subprocess,fcntl,os,yaml
owner=pathlib.Path.cwd();base=owner.parent/'autonomy_20261004';turn=base/'turns/001287';review=base/'turns/001284/independent-final-review';coord=owner/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 p=pathlib.Path(p);b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,d):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
def handle(pid):
 p=pathlib.Path(f'/proc/{pid}/stat')
 if not p.exists():return dict(pid=pid,absent=True)
 v=p.read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(v[19]),state=v[0])
r=json.loads((review/'report-v1.json').read_text());previous=json.loads((base/'turns/001286/operational-summary.json').read_text())
assert r['status']=='FINAL_SOURCE_CPU_PACKAGE_ACCEPTED_EXECUTION_NOT_RELEASED' and r['blockers']==[]
assert json.loads((review/'executor-exit-v1.json').read_text())['exit']==0
assert json.loads((base/'turns/001286/receipt.json').read_text())['status']=='completed_turn'
assert all(handle(p).get('absent') for p in [691500,691501,391755])
assert handle(268073)['start_ticks']==97715947 and handle(702807)['start_ticks']==146865708
for v in r['bindings'].values():
 if isinstance(v,dict) and 'path' in v and 'sha256' in v:assert ref(v['path'])['sha256']==v['sha256'],v['path']
work=pathlib.Path(json.loads((review/'authority-v1.json').read_text())['worktree'])
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=work,text=True).strip()==r['source_commit']
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==previous['source_commit']
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=work,text=True).strip()
assert not any(os.path.lexists(p) for p in previous['STOP'])
now=datetime.datetime.now(datetime.timezone.utc);assert now<datetime.datetime.fromisoformat(previous['deadline'].replace('Z','+00:00'))
next_action='Adopt independently accepted N36R2 source30c6321715df86c5bab623db607bab2811aed56d and finite accounting references under owner locks after reconciliation; establish bounded current readiness, then obtain input-bound B5 review, freeze final plan, root production review and detached release. Reuse accepted unchanged provenance. No dispatch until these gates pass.'
rec=dict(schema='n36r2-independent-final-review-terminal-reconciliation-v1',turn=1287,at=now.isoformat(),status='CPU_FINAL_PACKAGE_ACCEPTED_EXECUTION_NOT_RELEASED',report=ref(review/'report-v1.json'),exit=ref(review/'executor-exit-v1.json'),source_commit=r['source_commit'],owner_source=previous['source_commit'],absent_handles=[691500,691501,391755],driver=handle(268073),coordinator=handle(702807),ledger_prefixes=previous['ledger_prefixes'],retained_attempts=504,retained_gpu_hours=75.49265038509455,source_adopted=False,release_enabled=False,gpu_dispatch=False,target_met=False,next_action=next_action)
with open(owner/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for v in previous['ledger_prefixes'].values():assert ref(v['path'])['sha256']==v['sha256']
 put(turn/'entry-reconciliation-v1.json',rec);put(turn/'terminal-reconciliation-v1.json',rec)
 s=yaml.safe_load((owner/'research-state.yaml').read_text());c=json.loads((coord/'checkpoint.json').read_text())
 for x in [s,c]:
  item=x['n36r2_independent_final_review'];item['status']=rec['status'];item['historical_handles']=item.pop('handles',{});item['live_handles']=[];item['report']=rec['report'];item['terminal_reconciliation']=ref(turn/'terminal-reconciliation-v1.json')
  x['next_action']=next_action;x['updated_at']=rec['at']
 put(coord/'checkpoint.json',c)
 p=owner/'research-state.yaml';tmp=p.with_suffix('.yaml.tmp');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(p)
 t=json.loads((coord/'idea_tree.json').read_text());n=t['nodes']['15.6'] if isinstance(t['nodes'],dict) else next(n for n in t['nodes'] if n['id']=='15.6')
 n['result']='N36R2_FINAL_CPU_PACKAGE_ACCEPTED_EXECUTION_NOT_RELEASED';n['insight']='Independent final-source CPU package review passed with no bounded blocker; owner adoption/current readiness/final B5/frozen-plan/root-review/release remain pending. CPU evidence is not actual-worker validity or scientific promotion.';n['n36r2_independent_final_review']=ref(turn/'terminal-reconciliation-v1.json');put(coord/'idea_tree.json',t)
summary=dict(previous);summary.update(turn=1287,at=rec['at'],status=rec['status'],handles={},historical_review_handles=previous['handles'],driver=rec['driver'],coordinator=rec['coordinator'],review_terminal_exit_present=True,terminal_reconciliation=ref(turn/'terminal-reconciliation-v1.json'),prior_turn_receipt=ref(base/'turns/001286/receipt.json'),completed_work='Reconciled normal reviewer exit0, absent reviewer/controller handles, exact reviewed input hashes and both source heads. Accepted CPU-only independent final-source verdict; updated owner state/checkpoint/tree under state lock. All private ledger bytes unchanged. No source adoption, readiness operation, release or dispatch.',next_action=next_action,unresolved_evidence=['Owner adoption, current readiness and final B5/frozen-plan/root-review/detached-release remain pending.','Actual-worker validity and original validation/formal/required ablation evidence remain unmet.'])
put(turn/'operational-summary.json',summary)
(turn/'operational-summary.md').write_text('Turn001287: owner ca4e6a96d049c7ebb1f302d755883388ddbfdbd8; reviewed isolated source30c6321715df86c5bab623db607bab2811aed56d. Independent reviewer exited0; wrapper691500/executor691501 and old GPU controller391755 absent. Driver268073/start97715947 and coordinator702807/start146865708 verified on boot2a1fa95f-ab0d-488c-a298-fc488ddd2af7. CPU final package accepted; state/checkpoint/tree reconciled. All three ledger prefixes unchanged,504 attempts/75.49265038509455 GPUh retained. No STOP; deadline2026-10-11T11:13:13Z. '+next_action+' Original validation/formal/ablation goal unmet.\n')
(turn/'operational-summary.sha256').write_text(ref(turn/'operational-summary.json')['sha256']+'  operational-summary.json\n')
print(json.dumps({'status':rec['status'],'summary':str(turn/'operational-summary.md'),'ledger_unchanged':True}))
