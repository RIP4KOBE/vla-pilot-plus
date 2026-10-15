from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, hashlib, yaml
base=Path("artifacts/stage_closed_loop_20260929")
out=base/"attribution_20261001"
out.mkdir(exist_ok=True)
names={
 "V13":"codex_only_v13_historical_initialization_online_full10",
 "V14":"codex_partial_visibility_v14_historical_initialization_online_full10",
 "V15":"codex_contact_radius_v15_historical_initialization_online_full10",
 "V16":"codex_fused_carry_v16_historical_initialization_online_full10",
 "V17":"codex_failed_contact_v17_historical_initialization_online_full10"}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p): return [json.loads(s) for s in p.read_text().splitlines() if s]
def diff(a,b,p=""):
 if isinstance(a,dict) and isinstance(b,dict):
  return [r for k in sorted(set(a)|set(b)) for r in diff(a.get(k),b.get(k),f"{p}.{k}" if p else k)]
 return [] if a==b else [{"path":p,"before":a,"after":b}]
data={}
evidence={}
for v,n in names.items():
 r=base/"runs"/n
 events=rows(r/"output/eds_eval/stage_events.jsonl")
 actions=rows(r/"output/eds_eval/safety_events.jsonl")
 compute=rows(r/"output/eds_eval/episode_compute.jsonl")
 audit=json.loads((r/"audit.json").read_text())
 data[v]={"run":r,"events":events,"actions":actions,"config":yaml.safe_load((r/"resolved-config.yaml").read_text())}
 transports=[e["transport"] for e in events if e.get("query_status")=="ok"]
 evidence[v]={"valid":audit["valid"],"success":audit["success"],"episodes":audit["episodes"],
  "success_tasks":[e["task"] for e in audit["per_task"] if e["success"]],
  "provider_completed_calls":sum(e["provider_completed_turns"] for e in compute),
  "provider_failed_calls":sum(e["provider_failed_calls"] for e in compute),
  "model_settings":sorted(set((t.get("backend"),t.get("auth_mode"),t.get("model"),t.get("reasoning_effort")) for t in transports)),
  "action_count":len(actions),"overrides":sum(e["override"] for e in actions),
  "ignored_explicit_occluded_held_events":[{"task":e["task_id"],"step":e["global_step"]} for e in events if e.get("query_status")=="ok" and (e.get("control_observation") or {}).get("grasp")=="held" and (e.get("control_observation") or {}).get("support")=="unsupported" and (e.get("control_observation") or {}).get("target_visibility")=="occluded" and e["stage_after"]==1],
  "input_files":[{"path":str(r/f),"sha256":sha(r/f)} for f in ["audit.json","resolved-config.yaml","output/eds_eval/stage_events.jsonl","output/eds_eval/safety_events.jsonl","output/eds_eval/episode_compute.jsonl"]]}
pairs={}
for a,b in [("V13","V14"),("V14","V15"),("V14","V16"),("V16","V17"),("V13","V17")]:
 action_pairs=[]
 for task in range(10):
  aa=[e["executed_action"] for e in data[a]["actions"] if e["task_id"]==task]
  bb=[e["executed_action"] for e in data[b]["actions"] if e["task_id"]==task]
  first=next((i for i,(x,y) in enumerate(zip(aa,bb)) if x!=y),None)
  action_pairs.append({"task":task,"before_actions":len(aa),"after_actions":len(bb),"first_shared_action_difference":first,"full_equal":aa==bb})
 dd=diff(data[a]["config"],data[b]["config"])
 administrative={"main.eds_eval.job_id","main.eds_eval.output_dir","perception.gemini.capture_dir"}
 pairs[a+"->"+b]={"config_diff":dd,"scientific_config_diff":[x for x in dd if x["path"] not in administrative],"actions":action_pairs}
def compact(e):
 obs=e.get("control_observation") or {}
 tr=e.get("transport") or {}
 return {"step":e["global_step"],"stage":e["stage_after"],"ED":e["guidance_after"],"visual_hold":e["visual_hold"],"query_status":e["query_status"],
 "observation":{k:obs.get(k) for k in ["grasp","support","target_location","target_visibility"]},
 "request_fingerprint":tr.get("request_fingerprint"),"contact_phase":e["contact_phase"],"contact_until":e["contact_until"],
 "reward_reference_reset":e["reward_reference_reset"],"reason":e["stage_decision_reason"],
 "recheck":e.get("failed_contact_recheck")}
windows=[]
for a,b,task,steps in [("V13","V14",3,[80,96]),("V13","V14",8,[160,176]),("V16","V17",9,[24,40,56,64,72,88])]:
 aa={e["global_step"]:e for e in data[a]["events"] if e["task_id"]==task}
 bb={e["global_step"]:e for e in data[b]["events"] if e["task_id"]==task}
 for step in steps:
  x,y=compact(aa[step]),compact(bb[step])
  fp1,fp2=x["request_fingerprint"] or {}, y["request_fingerprint"] or {}
  both=bool(fp1 and fp2)
  windows.append({"before":a,"after":b,"task":task,"step":step,"before_event":x,"after_event":y,
   "same_categorical_observation":x["observation"]==y["observation"] if both else None,
   "same_transmitted_image":fp1.get("image_png_sha256")==fp2.get("image_png_sha256") if both else None,
   "same_prompt":fp1.get("prompt_sha256")==fp2.get("prompt_sha256") if both else None})
assert evidence["V13"]["success"]==0 and evidence["V17"]["success"]==3
assert evidence["V13"]["provider_completed_calls"]==437 and evidence["V17"]["provider_completed_calls"]==325
assert len(evidence["V13"]["ignored_explicit_occluded_held_events"])==15
assert pairs["V13->V14"]["actions"][3]["first_shared_action_difference"]==96
assert pairs["V13->V14"]["actions"][8]["first_shared_action_difference"]==176
assert pairs["V16->V17"]["actions"][9]["first_shared_action_difference"]==56
a=json.loads((data["V13"]["run"]/"manifest.json").read_text())["source_sha256"]
b=json.loads((data["V17"]["run"]/"manifest.json").read_text())["source_sha256"]
source_comparison={"changed_common_sources":[n for n in a if n in b and a[n]!=b[n]], "added_sources":sorted(set(b)-set(a)), "equal_common_sources":[n for n in a if n in b and a[n]==b[n]]}
result={"created_local":datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),"scope":"Read-only comparison of existing frozen full cohorts; no API or GPU experiment dispatched","versions":evidence,"pairs":pairs,"critical_windows":windows,"v13_to_v17_source_comparison":source_comparison,
 "limitations":["Fresh identity texts differ; matching images and categorical observations do not imply byte-identical full prompts","One development cohort per version; no held-out or replicated effect estimate","V16 branch derives from V14, not V15","This does not retroactively attribute the earliest legacy-interface Codex0/10 solely to later evidence-controller rules"]}
(out/"evidence.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"versions":{v:{k:d[k] for k in ["success","success_tasks","provider_completed_calls","provider_failed_calls"]} for v,d in evidence.items()},
 "critical_pairs":[{k:w[k] for k in ["before","after","task","step","same_categorical_observation","same_transmitted_image","same_prompt"]} for w in windows],
 "result":str(out/"evidence.json")},ensure_ascii=False,indent=2))

