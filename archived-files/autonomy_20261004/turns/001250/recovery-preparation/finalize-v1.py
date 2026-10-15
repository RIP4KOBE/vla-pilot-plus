import os,sys,json,hashlib,subprocess,datetime as dt
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=Path.cwd().resolve()
OWNER=Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree')
BASE='e95745853ec2fbb95e55915e99644a4dc0443261'
START=dt.datetime.fromisoformat('2026-10-10T02:21:13+00:00')
STOPS=[OWNER.parent/'autonomy_20261004/STOP',ROOT.parents[2]/'autonomy_20261004/STOP']
def sha(path):
    assert not any(s in str(path).lower() for s in ('poe','superpowers','2026-08-10-eds-qd-stage-guidance-transition-design'))
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def ref(path):
    p=Path(path).resolve();return {'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
def read(name):return json.loads((OUT/name).read_text())
def write(name,value):
    p=OUT/name;assert not p.exists();p.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');return ref(p)
def git(root,*args):return subprocess.check_output(['git','--no-optional-locks','-C',str(root),*args]).decode().strip()
now=dt.datetime.now(dt.timezone.utc)
assert now<dt.datetime.fromisoformat('2026-10-11T11:13:13+00:00') and (now-START).total_seconds()<1800
assert not any(os.path.lexists(p) for p in STOPS)
before=read('preservation-before-v1.json')
for record in before['ledgers'].values():assert sha(record['path'])==record['sha256'] and Path(record['path']).stat().st_size==record['bytes']
assert sha(before['state']['path'])==before['state']['sha256']
assert git(OWNER,'rev-parse','HEAD')==before['owner_head']=='ca4e6a96d049c7ebb1f302d755883388ddbfdbd8'
assert git(ROOT,'status','--porcelain')==''
commit=git(ROOT,'rev-parse','HEAD');assert git(ROOT,'rev-parse','HEAD^')==BASE
subprocess.run(['git','diff','--check',BASE,commit],check=True,cwd=ROOT)
patch=subprocess.check_output(['git','diff','--binary',BASE,commit],cwd=ROOT)
(OUT/'source-changes-v1.patch').write_bytes(patch)
changed=git(ROOT,'diff','--name-only',BASE,commit).splitlines()
source_files=[ref(ROOT/name) for name in changed]
prepared=read('preparation-result-v1.json');coverage=read('source-coverage-v1.json');runtime=read('runtime-payload-reuse-v1.json');native=read('native-binding-v1.json')
accounting=read('accounting-snapshot-v1.json');bootstrap=read('bootstrap-parent-checks-v1.json');parent=read('captured-runtime-parent-checks-v1.json');negative=read('draft-negative-checks-v1.json')
plan=read('draft/plan.partial.draft-v1.json');closure=read('runtime-closure.n36r2.draft-v1.json')
assert not plan['release_enabled'] and not plan['frozen'] and plan['authority'] is None and plan['execution_release'] is None
preservation=write('preservation-after-v1.json',{'owner_head':before['owner_head'],'owner_source_unchanged':True,
    'research_state_unchanged':True,'private_ledgers_unchanged':True,'ledger_prefixes':before['ledgers'],
    'state':before['state'],'isolated_commit':commit,'isolated_tracked_status':'clean',
    'stops':{str(p):os.path.lexists(p) for p in STOPS},'at':now.isoformat()})
bindings=write('source-runtime-native-accounting-bindings-v1.json',{'source_commit':commit,'accepted_base':BASE,
    'source_record':prepared['source'],'source_coverage_complete':False,'changed_source_files':source_files,
    'runtime_closure':prepared['runtime_closure'],'runtime_payload':closure['runtime'],'native_build':prepared['native_build'],
    'accounting':prepared['accounting'],'allocation':prepared['allocation'],'protocol':prepared['protocol'],'plan':prepared['plan'],
    'cpu_context':prepared['context'],'cpu_receipt':ref(OUT/'cpu-receipt-v1.json'),
    'runtime_closure_accepted':False,'source_adopted':False,'gpu_authorized':False,'release_enabled':False})
blockers=[
 {'id':'B1','gate':'canonical STOP','detail':'Unchanged production stop_path resolves to the data-volume session STOP; canonical owner STOP is a different path. Both were checked by this executor. No relocated STOP is treated as owner authority.',
  'next':'Independent review of an exact canonical-owner plus relocated STOP check throughout admission/healthcheck/worker lifecycle, or use a checkout whose supported layout already binds canonical owner STOP. Do not simply change a plan string.'},
 {'id':'B2','gate':'complete source freeze','detail':'Production source_paths includes scripts/qd_ed_poe_launch.py. It was deliberately omitted from the permitted source record under the no-Poe restriction. The record is explicitly incomplete; full verify_sources/prepare was not bypassed or claimed to pass.',
  'next':'Root must resolve the source-inventory/policy conflict before a complete production source freeze. A partial record is not adoptable.'},
 {'id':'B3','gate':'compiled-source parent receipt','detail':bootstrap['error'],
  'evidence':ref(OUT/'bootstrap-parent-checks-v1.json'),'observed_analysis':negative['frozen_alias_failure_analysis'],
  'next':'Review a bounded frozen os.path/posixpath identity treatment in source-execution receipts, retaining interpreter binding and ordinary-module checks; regenerate process-bound receipts only after reviewed source changes. Do not whitelist missing compiled files.'},
 {'id':'B4','gate':'runtime checkout composition','detail':'Payload references and all 3291 file hashes are verified, but the retained immutable runtime still identifies owner checkout paths/PYTHONPATH. The partial plan identifies the isolated checkout. No complete production runtime-input composition or controller rebind is claimed.',
  'next':'Materialize or accurately link allowed non-source runtime assets and create a separate source-bound runtime/controller rebind; verify supported layout and every relocated byte. Preserve the historical runtime.'},
 {'id':'B5','gate':'production recovery admission/release','detail':'N36R2 support is deliberately draft-only. Both validate_plan and pre_dispatch explicitly reject N36R2. No detached release, root approval, live after-episode attestation or GPU permission was produced.',
  'next':'Independent/root review of source and artifacts; separately implement/review any finite N36R2 production admission/accounting/resource support after the other blockers. These drafts cannot be activated by changing flags.'}
]
report={'schema':'node-15.6-n36r2-bounded-cpu-preparation-report-v1','node_id':'15.6','status':'BLOCKED_PARTIAL_DRAFT_PRESERVED_FOR_INDEPENDENT_REVIEW',
 'at':now.isoformat(),'workspace':str(ROOT),'report_directory':str(OUT),'source_base':BASE,'source_commit':commit,
 'source_branch':git(ROOT,'branch','--show-current'),'source_changed_files':changed,'source_patch':ref(OUT/'source-changes-v1.patch'),
 'owner_commit':before['owner_head'],'source_adopted':False,'bindings':bindings,
 'implementation':['Finite N36R2_NONPROGRESS_TANGENT_DEV_001250 draft identity with n36r2/001250 keys, original N36 and N36R1 anchors retained.',
   'Strict allocation/protocol/accounting inheritance, exact old scientific protocol and review digests, retained charges and zero automatic recovery.',
   'Explicit N36R2 production release and pre-dispatch rejection; old production recovery validator unchanged.',
   'CPU bootstrap diagnostic calls actual live runtime/source attestors and creates separately scoped receipts without Main, simulator, model/provider or device execution.'],
 'drafts':{'allocation':prepared['allocation'],'protocol':prepared['protocol'],'accounting':prepared['accounting'],'plan':prepared['plan'],
   'episode_count':40,'all_keys_fresh':True,'all_output_directories_fresh_and_absent':True,
   'scientific_tasks_seeds_arms_order_thresholds_algorithms_unchanged':True,
   'comparison':ref(OUT/'all40-partial-composition-v1.json'),'complete_production_composition':False},
 'runtime':{'closure':prepared['runtime_closure'],'ordinary_inventory_count':len(closure['modules']),'ordinary_inventory_unchanged':True,
   'ordinary_inventory_digest':hashlib.sha256(json.dumps(closure['modules'],sort_keys=True).encode()).hexdigest(),
   'module_aliases':closure['module_aliases'],'required_after':closure['required_after'],'generated_modules':closure['generated_modules'],
   'interpreter':closure['interpreter'],'distributions':closure['distribution_versions'],'payload_reuse':ref(OUT/'runtime-payload-reuse-v1.json'),
   'native_build':prepared['native_build'],'native_libraries':native['libraries'],'native_static_hashes_verified':True,
   'runtime_closure_accepted':False,'native_gpu_evaluation':False},
 'accounting':{'snapshot':ref(OUT/'accounting-snapshot-v1.json'),'dispatched':accounting['dispatched'],'gpu_hours_consumed':accounting['gpu_hours_consumed'],
   'decimal_seconds_sum':accounting['decimal_seconds_sum'],'decimal_hours_sum':accounting['decimal_hours_sum'],
   'arithmetic_note':'Retained GPUh matches exact binary-float production accumulation. Decimal sum of recorded decimal strings is also provided; it differs only by accumulation rounding and is not substituted into the ledger.',
   'preserved_attempts':accounting['preserved_attempts'],'protected_gpu_hour_caps':accounting['protected_gpu_hours'],
   'protected_gpu_hours_remaining_by_production_formula':{k:max(0.,v-accounting['gpu_hours_by_bucket'][k]) for k,v in accounting['protected_gpu_hours'].items()},
   'protected_attempt_caps':accounting['protected_attempts'],'no_new_budget_authority':True,'ledger_writes':False,
   'n36_primary_disposition':'INVALID; charge retained','n36r1_disposition':'INVALID; charge retained; no replay or rehabilitation'},
 'checks':{'identity_tests':{'result':'12 passed','evidence':ref(OUT/'identity-tests-v1.json')},
   'draft_structure':{'positive':1,'negative_rejections':len(negative['checks'])-1,'evidence':ref(OUT/'draft-negative-checks-v1.json')},
   'static_checks':prepared['checks'],'actual_bootstrap':{'exit_code':bootstrap['exit_code'],'process':bootstrap['process'],
      'evidence':ref(OUT/'bootstrap-parent-checks-v1.json'),'live_runtime_and_source_attestors':'PASS; emitted actual receipt','compiled_source_parent_gate':'FAIL'},
   'runtime_parent':{'positive_snapshots':2,'negative_rejections':6,'evidence':ref(OUT/'captured-runtime-parent-checks-v1.json'),
      'scope':'actual production receipt binding and runtime parent attestor; after=False for both CPU snapshots; no full worker parent verification'},
   'git_diff_check':'PASS','tracked_status':'clean'},
 'execution_notes':[
   'Initial combined pytest run was SIGTERM-stopped after 20.72 seconds with 47 progress dots and no final test result. Its composition fixture hashes all scripts and could have opened the prohibited Poe launcher before interruption. No file-open audit was installed for that initial run, so no claim of no-Poe file access is made for it. No contents were displayed and no Poe/provider execution occurred. This run is not counted as passing scoped evidence.',
   'Subsequent focused identity tests and preparation used a prohibited-path open guard. Initial guard also falsely rejected dependency source huggingface_hub/utils/_git_credential.py; this is package code, not stored credentials. A new preparation script kept secret-file guards and allowed package code. The failed artifact was retained.',
   'First partial composition comparison rejected relocated diagnostic run_id/output_dir and tuple-vs-JSON-list representation. A separate finish script canonicalized JSON and normalized only prospective source/run/output bindings; scientific values remained exact. Prior failures are retained.',
   'Pinned RDT/LeRobot source/config files restored from existing local Git objects into isolated worktree only. No packages installed, network fetch, owner checkout change or submodule pointer change.',
   'No broader or repeated suite was run after bounded focused checks. Captured v3 parent checks reuse the single actual child receipt; no worker rerun or simulator/native GPU evaluation.'
 ],
 'scope_incident':{'initial_pytest_prohibited_file_hashing_possible':True,'initial_test_evidence_accepted':False,'evidence':ref(OUT/'focused-tests-v1.json')},
 'blockers':blockers,'preservation':preservation,
 'resource_limits':{'python':'/home/hynx/miniconda3/envs/vla-pilot/bin/python','CUDA_VISIBLE_DEVICES':'','max_threads':2,
     'affinity_for_checks':[0,1],'check_cpu_limit_seconds':1200,'wall_limit_seconds':1800,
     'elapsed_wall_seconds_since_first_guard':(now-START).total_seconds(),
     'enforcement':'Bounded check scripts used RLIMIT_CPU 120/300/600 or 1200, two-CPU affinity and two-thread environment; subprocess waits had finite timeouts. Measured check times are retained per artifact; no exact all-command aggregate CPU measurement was available.',
     'bootstrap_cpu_seconds':bootstrap['cpu_seconds'],'bootstrap_wall_seconds':bootstrap['wall_seconds']},
 'prohibitions':{'agents_spawned':False,'gpu_dispatch':False,'simulator_episodes':False,'provider_calls':False,'packages_installed':False,
     'owner_state_or_ledger_writes':False,'protected_results_opened':False,'credentials_opened':False,'prohibited_design_opened':False,
     'superpowers_used':False,'old_records_modified':False},
 'review_required':True,'release_enabled':False,'gpu_authorized':False,'scientific_promotion':False,'target_met':False,'worktree_preserved':True}
write('report-v1.json',report)
markdown=f'''N36R2 preparation is **blocked; disabled partial drafts are preserved for independent review**.

Source commit: `{commit}` on `{report['source_branch']}`, based on accepted `{BASE}`. Owner remains `{before['owner_head']}`. Six source/test files changed; tracked worktree is clean. No adoption or release activation occurred.

Prepared 40 fresh `n36r2_*_001250` identities and absent output directories, strict allocation/protocol/accounting drafts, and all 40 partial manifests. Scientific tasks, seeds, arms, order, thresholds and algorithms match the inherited cohort. N36R2 production release and admission are explicitly disabled in source.

The prospective closure retains all **{len(closure['modules'])} ordinary inventory entries**, interpreter/distribution bindings and generated rules. Its explicit `_cyutility` rule permits only the three already-frozen qualified native targets. All 3,291 existing runtime payload files and {native['libraries']} native library records were hash-verified. Historical runtime references are retained accurately; an isolated-runtime rebind is still incomplete.

Private ledger arithmetic matches **504 dispatches / 75.49265038509455 GPUh**. Primary N36 **86.40354533703066 seconds** and N36R1 **809.4826372319367 seconds** remain charged and INVALID. The report includes both unchanged production float accumulation and exact decimal-string summation. Protected reserve caps remain 32/12 GPUh and 180/40 attempts. Owner state and all three private ledgers remain byte-identical.

Validation: **12 focused identity tests passed**; the actual draft passed structural validation and **16 negative probes** were rejected. The actual source-only bootstrap exited 0 and emitted live receipts. Both process-bound v3 runtime snapshots passed the production parent attestor; six binding/identity mutations were rejected. CPU snapshots use `after=False`; they are not full post-episode coverage.

Blocking gates:

- Canonical owner STOP differs from the production STOP derived from the relocated worktree. Both were checked; no guard was weakened.
- Complete production source inventory requires the prohibited Poe launcher. The permitted-source record excludes it and is explicitly incomplete.
- Actual compiled-source parent verification fails: `N36 module missing executable receipt: .../posixpath.py`. Captured evidence shows `os.path` aliases frozen `posixpath`; no exception was added.
- Runtime payload paths/PYTHONPATH still name the owner checkout. Full production runtime/controller rebind remains outstanding.
- Draft-only N36R2 production support and every artifact require independent/root review; no detached release exists.

The initial combined pytest run was stopped because its fixture hashes every script, potentially including the excluded Poe launcher. File access was not audited in that run, so absence of such hashing cannot be certified. Its 47 progress dots are **not** counted as a passing result. No Poe/provider execution occurred. Later narrow preparation used explicit path guards. Both preliminary preparation/comparison failures are retained.

Next: independently review this source and the hash-bound partial artifacts; resolve the STOP and source-inventory conflicts, review the frozen-alias source-receipt failure, then complete a fresh runtime/controller composition. Do not adopt the partial source record, reuse historical episode directories, or activate these drafts by flipping flags. No agents, GPU evaluation, simulator episodes, provider calls, package installs, owner writes, replay, rehabilitation or scientific promotion were performed.

Detailed bindings and actual commands/results are in `report-v1.json`, `source-runtime-native-accounting-bindings-v1.json`, and `sha256-manifest-v1.json`. Wall time at report generation: {(now-START).total_seconds():.1f} seconds, below the 1,800-second bound.
'''
(OUT/'report-v1.md').write_text(markdown)
# Explicit generated artifact families only; exclude mutable executor/controller logs.
files=[]
for p in sorted(OUT.rglob('*')):
    if not p.is_file():continue
    if p.name.startswith(('executor-','wrapper')) or p.name in ('sha256-manifest-v1.json','sha256-manifest-v1.txt'):continue
    files.append(ref(p))
manifest={'schema':'n36r2-preparation-sha256-manifest-v1','source_commit':commit,'files':files,'changed_source_files':source_files,
          'external_bindings':{'native_build':prepared['native_build'],'runtime':closure['runtime'],'private_ledger_prefixes':before['ledgers']},
          'excluded_mutable_artifacts':['executor-*','wrapper*'],'release_enabled':False}
write('sha256-manifest-v1.json',manifest)
(OUT/'sha256-manifest-v1.txt').write_text(''.join(f"{r['sha256']}  {r['path']}\n" for r in files+source_files))
print(json.dumps({'report':str(OUT/'report-v1.json'),'commit':commit,'status':report['status'],'manifest_files':len(files),'wall_seconds':(now-START).total_seconds()},indent=2))
