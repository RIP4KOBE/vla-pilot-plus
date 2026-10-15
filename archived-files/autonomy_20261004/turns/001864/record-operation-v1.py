from pathlib import Path
import json,hashlib,datetime,fcntl,os,yaml
root=Path.cwd();base=(root/'../autonomy_20261004').resolve();out=base/'turns/001864'
def ref(p):return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
prev=json.loads((base/'turns/001863/operational-summary-v1.json').read_text());live=json.loads((out/'live-reconciliation-v1.json').read_text());process=json.loads((out/'cpu-operation-process-v1.json').read_text());now=datetime.datetime.now(datetime.timezone.utc).isoformat()
result=json.loads((out/'audit-result-v1.json').read_text()) if (out/'audit-result-v1.json').exists() else None
status=result['status'] if result else 'RUNNING_CPU_DISABLED_GRAPH_ADMISSION_ALL41'
for h in [process['wrapper'],process['child']]:
 p=Path('/proc')/str(h['pid'])/'stat'
 if p.exists():
  fields=p.read_text().rsplit(')',1)[1].split();h.update(alive=int(fields[19])==h['start_ticks'] and fields[0]!='Z',state=fields[0])
 else:h.update(alive=False,state='absent')
next_step='Monitor turn001864 CPU production disabled-graph admission using recorded wrapper/child boot/start identities; do not restart or duplicate. On terminal result reconcile exact failure or PASS, then fresh finite readiness accounting/release and independent review. Source and scientific gates unchanged; no GPU dispatch until required gates pass; STOP/deadline 2026-10-11T11:13:13Z.'
record=dict(status=status,at=now,source=prev['current_source'],graph=ref(out/'graph.complete-disabled-v1.json'),process_record=ref(out/'cpu-operation-process-v1.json'),handles=[process['wrapper'],process['child']],script=ref(out/'audit-disabled-graph-v1.py'),wrapper_script=ref(out/'audit-wrapper-v1.py'),result_path=str(out/'audit-result-v1.json'),exit_path=str(out/'audit-exit-v1.json'),stderr_path=str(out/'audit.stderr.log'),gpu_authorized=False,release_enabled=False)
if result:record['result']=ref(out/'audit-result-v1.json')
summary=dict(schema='autonomy-operational-summary-v1',at=now,turn=1864,current_source=prev['current_source'],owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles=live['driver_handles'],cpu_operation_handles=record['handles'],controller_status='NO_LIVE_EXPERIMENT_CONTROLLER_CPU_ADMISSION_'+status,ledger_prefixes=prev['ledger_prefixes'],ledgers_unchanged=True,completed_work=['Verified bound authority, STOP/deadline, driver and all recorded owning process identities; no live experiment controller.','Composed fresh disabled successor graph with accepted exact four-predecessor reconciliation and reviewed controller binding.','Rebound specification, scope, accounting, all40 manifests, separate engineering manifest and plan; preserved scientific source and thresholds.','Started exact production CPU graph admission, with network/GPU/provider disabled; process identity and terminal-result paths retained.'],graph=record['graph'],operation=record,next_bounded_step=next_step,unresolved_evidence=['CPU production admission outcome','Fresh readiness accounting/release and independent review','Valid native engineering execution','Original validation/formal/required ablation evidence'],target_met=False,stop_present=(base/'STOP').exists(),deadline='2026-10-11T11:13:13Z')
cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for r in prev['ledger_prefixes'].values():assert ref(Path(r['path']))['sha256']==r['sha256']
 p=out/'operational-summary-v1.json'
 with p.open('x') as f:json.dump(summary,f,indent=2);f.write('\n')
 sr=ref(p);(out/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n')
 for p,isyaml in [(root/'research-state.yaml',True),(cp,False)]:
  d=yaml.safe_load(p.read_text()) if isyaml else json.loads(p.read_text());d.update(n36_successor_disabled_graph_admission=record,latest_operational_summary=sr,next_action=next_step,updated_at=now);tmp=p.with_name(p.name+'.001864.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False) if isyaml else json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
print(json.dumps(dict(summary=sr,status=status,handles=record['handles'])))
