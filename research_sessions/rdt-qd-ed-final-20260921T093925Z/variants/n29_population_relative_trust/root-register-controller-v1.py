"""Synchronize operational continuation records; no new execution authority."""
from pathlib import Path
import datetime,json,os,sys,yaml
V=Path(__file__).resolve().parent;ROOT=V.parents[1]/'study_worktree';sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n29_contract as c
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
controller=c.ref(V/'execution/controller-process-v1.json');identity=w.read_ref(controller)
assert Path(f'/proc/{identity["pid"]}/stat').read_text().rsplit(')',1)[1].split()[19]==identity['proc_start_ticks']
session=ROOT/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z';coord=session/'.coordinator'
with r.locked(ROOT/'data/qd-ed-state.lock'):
    state=r.read_state(ROOT/'research-state.yaml');c.require_budget_state(state,vars(r))
    state['study']['status']='N29_DEV_CONTROLLER_STARTED_TARGET_NOT_MET'
    state['current_iteration'].update(status='N29_DEV_CONTROLLER_STARTED',controller=controller)
    state['next_action']='Monitor the one finite N29 Dev controller; inspect Codex-only Stage usage and exact accepted outcomes. Do not resume or retry a terminal cohort. Review the terminal result before the next hypothesis.'
    target=ROOT/'research-state.yaml';tmp=target.with_suffix('.yaml.n29-registration-tmp')
    with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
    os.replace(tmp,target)
    cp_path=coord/'checkpoint.json';cp=json.loads(cp_path.read_text())
    cp.update(status='N29_DEV_CONTROLLER_STARTED',active_controller=identity,active_node='13.1',in_flight_executor=None,source_commit=state['source_commit'],next_action=state['next_action'])
    r.durable_json(cp_path,cp)
    tree_path=coord/'idea_tree.json';tree=json.loads(tree_path.read_text())
    node=tree['nodes']['13.1'];node.update(status='running',phase='MATCHED_DEV_RUNNING',gpu_execution_authorized=True,controller=controller,
        phase_b_review=c.ref(V/'root-phase-b-cpu-review-v1.json'),native_review=c.ref(V/'root-native-proof-review-v1.json'),
        frozen_plan=c.ref(V/'plan.frozen.v1.gpu7.json'),execution_release=c.ref(V/'execution-release-v1.json'),budget_authority=c.ref(c.BUDGET_AUTHORITY))
    r.durable_json(tree_path,tree)
    with (coord/'idea_tree.md').open('a') as f:f.write('\n'+now+' — 13.1 N29 MATCHED_DEV_RUNNING: accepted CPU/source/native proof; one frozen 40-cell maximum Dev controller, GPU7, Codex current managed login only. Target not met.\n')
    text=('\n## N29 execution activation '+now+'\n\n'
        'N29 source d855cfd690482e018bb40ce98edec80fad9700e0: 411 source files, 380 old files unchanged, three old files exactly reversible. CPU limitations and failed runs remain in the accepted review. Runtime/checkpoint/encoder bytes and original 40 Dev identities verified. One CUDA proof passed all 24 fixed cases, 17.575451474054717 GPU process seconds, zero models/API/simulator/episodes; cost retained.\n\n'
        'Root adopted the concrete finite proposal under the existing no-intervention delegation: cumulative 578 attempts / unchanged100 GPU hours, local13.5 GPU hours, baseline76/development262/validation180/formal40/recovery20, protected validation32/formal12 hours. This is not a separate numerical user approval; the last explicit395/100 approval chain remains intact. Forty worst-case episodes need more than local13.5h, so full-attempt reservation may close RESOURCE_BUDGET_INCOMPLETE.\n\n'
        'Frozen task-major tasks0..9 × C0/Q0/N28/N29, no result inheritance or retry. Candidate Dev requires all40 valid, N29>=5/10 and >= matched C0/Q0 plus original validity/substantive-QD/ED gates. Stop only after a complete task block when success plus remaining candidate tasks is below5, or on invalidity/resource limits. Protected phases remain closed.\n\n'
        'Provider is official Codex CLI, current managed ChatGPT login, gpt-6-astra/low/180s; Poe and fallback disabled, stored Poe credentials untouched. Controller: '+controller['path']+' . Artifacts: '+str(V/'artifacts')+' . Original research target remains unmet.\n')
    with (session/'REPORT.md').open('a') as f:f.write(text)
    with (ROOT/'docs/03_evidence/qd_ed_final/iteration-ledger.md').open('a') as f:f.write(text)
    w.atomic_json(V/'root-controller-registration-v1.json',{'schema':'n29-root-controller-registration-v1','recorded_at':now,'controller':controller,'source_commit':state['source_commit'],'phase':'MATCHED_DEV_RUNNING','target_achieved':False,'provider':'codex_cli/chatgpt/current managed login','poe_allowed':False,'new_authority_created':False})
print(json.dumps({'registered':True,'controller_pid':identity['pid'],'gpu':7,'target_achieved':False}))
