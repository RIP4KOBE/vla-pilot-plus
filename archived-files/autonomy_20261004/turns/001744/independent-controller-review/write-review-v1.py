import datetime,hashlib,json,pathlib,subprocess
O=pathlib.Path(__file__).parent

def ref(path):
 p=pathlib.Path(path);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def read(path):return json.loads(pathlib.Path(path).read_text())
def write(name,value):
 with (O/name).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
a=read(O/'authority-v1.json');checks=read(O/'static-checks-v1.json');D=pathlib.Path(a['proposed_artifact_directory'])
m=read(D/'generated-artifact-manifest-v2.json');mi={pathlib.Path(r['path']).name:r for r in m['files']};c=read(mi['controller-semantics.json']['path']);r=read(c['runtime']['path']);cl=read(c['runtime_closure']['path']);s=read(r['preparation']['source_record']['path']);old=read(a['prior_root_acceptance']['path']);oldc=read(old['controller']['path'])
assert checks['failure_count']==0
# Recheck every bounded input against its captured identity before finalizing.
for saved in checks['input_files']:assert ref(saved['path'])==saved, saved['path']
extra=read(O/'adapter-delta-review-v1.json');assert ref(extra['source']['path'])==extra['source']
assert not any(pathlib.Path(p).exists() for p in a['stop_authority']['paths'])
assert subprocess.check_output(['git','rev-parse','HEAD','HEAD^{tree}'],cwd=a['source']['worktree'],text=True).splitlines()==[a['source']['commit'],a['source']['tree']]
site=pathlib.Path(c['source']['path']).parents[1];base=site/'controllers/base_controller.py';lines=base.read_text().splitlines()
review={
 'schema':'n36-final-controller-independent-review-v1',
 'node_id':'15.6','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'status':'PASS_SCOPED_STATIC_BINDINGS',
 'scope':'Independent static review only of final controller semantics and affected source/runtime/closure bindings at source 89506fe1d9e2c753b66f6d3349963f6e9b316560. This is a recommendation for owning-root acceptance, not acceptance or execution authority.',
 'authority':ref(O/'authority-v1.json'),
 'source':a['source'],
 'references':{
   'boundary_diagnosis':ref(a['boundary_diagnosis']['path']),
   'prior_root_acceptance':ref(a['prior_root_acceptance']['path']),
   'prior_accepted_controller':ref(old['controller']['path']),
   'prior_accepted_runtime':ref(old['runtime']['path']),
   'prior_accepted_closure':ref(old['runtime_closure']['path']),
   'proposal_report':ref(D/'report-v2.json'),
   'proposal_manifest':ref(D/'generated-artifact-manifest-v2.json'),
   'controller_proposal':ref(mi['controller-semantics.json']['path']),
   'source_record':ref(r['preparation']['source_record']['path']),
   'runtime':ref(c['runtime']['path']),
   'runtime_closure':ref(c['runtime_closure']['path']),
   'controller_evidence_proposals':{k:ref(v['path']) for k,v in c['review_evidence'].items()},
   'prior_accepted_controller_evidence':{k:ref(v['path']) for k,v in oldc['review_evidence'].items()},
   'static_checks':ref(O/'static-checks-v1.json'),
   'source_excerpts':ref(O/'source-excerpts-v1.json'),
   'adapter_delta_review':ref(O/'adapter-delta-review-v1.json')},
 'decision':{
   'eligible_for_owning_root_scoped_static_acceptance':True,
   'root_acceptance_granted':False,
   'existing_proposals_remain':'PENDING_INDEPENDENT_AND_ROOT_REVIEW',
   'reason':'Exact final references and scoped deployed-source identities pass independent verification; fixed semantics and instance expectations agree with installed source and prior accepted semantics. No inherited acceptance is transferred to projections.',
   'blocking_findings_within_scope':[]},
 'findings':[
  {'id':'FINAL_BINDINGS','result':'PASS','detail':'Controller and all three proposed deployed_source_review records bind the same runtime SHA-256 42c620342d84326e204fef74ff4c4e8e99bb3e5cf44c76cf759de3f80431906c and closure SHA-256 e5534da2256502ca09b740a340c5ce793f7af556825248f1b7d036a10e29430d. Closure.runtime equals controller.runtime. OSC source equals closure.modules[robosuite.controllers.osc] and OSC is required_after. Runtime preparation, source record, controller and proposals agree on final commit; worktree and Git tree agree with authority. All relevant direct reference hashes and supplied sizes pass.'},
  {'id':'PRIOR_ACCEPTANCE_CONTINUITY','result':'PASS','detail':'Turn001713 binds d3225489f6edfd2e49f472dc1ea9307f14f8be70, not this final commit. Direct prior controller and three source reviews were hash checked. Current findings, seven deployed source identities, class/module, semantic map and all 12 expected fields equal accepted prior values. Old-to-final runtime changes only preparation.source and preparation.source_record; closure changes only runtime reference. Four changed tracked paths comprise two operational scripts and their tests; scoped controller/adapter sources remain unchanged. Historical nested provenance was not recursively reopened.'},
  {'id':'SCALE_AND_GOALS','result':'PASS','detail':'base_controller.py:104-123 clips inputs then affine-scales; symmetric [-1,1] inputs and output bounds give translation .05 and rotation .5, preserving zero. osc.py:231-265 uses all six action channels in fixed mode, scales delta, adds translation to current end-effector position, and uses scaled axis-angle orientation. control_utils.py:133-136 and 174-177 implement position addition and left multiplication of delta rotation with current orientation. Config position/orientation limits are null. This proves command semantics, not measured physical gain; projector_0_01 remains a convention.',
   'world_pose_source':{'source':ref(base),'start_line':138,'end_line':144,'text':'\n'.join(f'{i}: {lines[i-1]}' for i in range(138,145))}},
  {'id':'ZERO_ROTATION','result':'PASS_WITH_EXPLICIT_LIMIT','detail':'osc.py:259-263 skips goal_ori assignment when scaled rotation is zero and set_ori is absent. It retains previous goal orientation, initialized/reset from the current end-effector orientation; it does not assign a fresh absolute pose or prove a physical orientation lock. Nonzero rotation is a scaled axis-angle increment relative to current orientation.'},
  {'id':'WRAPPER_AND_GRIPPER','result':'PASS_STATIC','detail':'libero_adapter.py constructs an empty postprocessor; local fallback preserves the transition. Pinned LeRobot pipeline alias/default converters were also read and hash checked: empty steps preserve the action tensor through batch_to_transition and transition_to_batch. Adapter clones action, maps final channel >0 to +1 and otherwise -1, converts to CPU float32 NumPy, and forwards through LiberoEnv.step and ControlEnv.step. OffScreenRenderEnv inherits OSC_POSE/Panda/default gripper/20Hz defaults. Robosuite RobotEnv slices per robot; SingleArm splits six arm channels from gripper and calls set_goal on policy steps. Panda default_gripper is PandaGripper; manipulator forwards to format_action, which increments and clips finger commands with -1 open/+1 close. No imported branch or actual instance was observed.'},
  {'id':'INSTANCE_FIELDS_AND_ADAPTER','result':'PASS_EXPECTED_CONFIGURATION','detail':'All 12 canonical fields were checked, including exact output magnitudes and uncouple_pos_ori=True. OSC constructor stores use_delta, use_ori, control_dim, impedance_mode, input/output arrays, control_freq, uncoupling and both interpolators. Controller factory forces orientation control for OSC_POSE and leaves interpolators None for null interpolation. SingleArm forwards control_freq as policy_freq. INSTANCE_ATTRIBUTES maps every canonical name to the correct installed attribute. These are expected values only.',
   'expected_instance':c['instance'],
   'instance_attributes':{'control_delta':'use_delta','control_ori':'use_ori','control_dim':'control_dim','impedance_mode':'impedance_mode','input_min':'input_min','input_max':'input_max','output_min':'output_min','output_max':'output_max','policy_freq':'control_freq','uncouple_pos_ori':'uncoupling','interpolator_pos':'interpolator_pos','interpolator_ori':'interpolator_ori'}},
  {'id':'VALIDATOR_AND_ACCEPTANCE_BOUNDARY','result':'PASS_STATIC_REVIEW_PENDING_ROOT','detail':'qd_ed_n34_controller.verify_semantics requires external ROOT_REVIEWED controller status, exact runtime reference, closure-loaded OSC source, fixed delta/no-interpolation shape, semantic map and exactly three deployed_source_review references. Current pending controller must fail that root-status gate. It was not executed or bypassed. The validator alone does not check proposal evidence status, every evidence source hash, evidence closure/source_commit, exact .05/.5 magnitudes or uncouple_pos_ori=True; this review independently checked those bindings and values. attest_instance checks actual class/file hash and equality of all mapped instance fields, and observe_instances requires at least one observation. Neither was executed. Root approval cannot be obtained by copying historical status.'},
  {'id':'RUNTIME_SOURCE_BOUNDARY','result':'PASS_SCOPED_ONLY','detail':'Affected worktree paths were positively identified as regular tracked Git blobs and compared with committed bytes and the source inventory. Pinned LeRobot sources were checked against superproject gitlink commit 715debf6c1723a28f1a57d4274a8c4ec35b6a417, not an arbitrary dependency HEAD. Relevant installed robosuite modules were hash checked against closure entries. Worktree application/LeRobot/LIBERO code is bound by source record and, where present, runtime.files; it need not be duplicated in external closure.modules. validate_runtime_binding still requires complete inventory and verify_source, while verify_runtime/attest_runtime require full module/interpreter/loaded-origin checks. Those whole-graph obligations were not claimed or run.'},
  {'id':'READINESS_AND_OPERATIONAL_DELTA','result':'NO_NEW_READINESS','detail':'Runtime provider_ready, cuda_egl_verified, preparation.runtime_ready and release_enabled remain false; provider_evidence is null and historical_readiness_is_not_current is true. Operational diffs add recovery-prefix validation and required-after producer import preparation. The latter explicitly requires later unchanged native/runtime/source receipts and does not instantiate a controller. This review neither revalidates recovery accounting nor produces measurements.'}
 ],
 'verification':{'static_check_count':len(checks['checks']),'failed_check_count':0,'all_captured_inputs_rehashed_before_finalization':True,'additional_readiness_adapter_git_and_inventory_check':True,'production_verify_semantics_executed':False,'production_verify_source_executed':False,'production_verify_runtime_executed':False,'method':'Standard-library static JSON/hash/AST reads and read-only Git; no project or installed ML-library imports; no tests, simulations or native/model/provider execution.'},
 'minimal_next_construction_step':{
   'actor':'Owning root coordinator, separately from this reviewer',
   'action':'Review and explicitly accept or reject this scoped result. If accepting, create new root acceptance sidecar and new root-reviewed controller/evidence records without editing these existing proposals. Bind this review hash, exact proposed controller and three evidence hashes, final source commit/tree/source-record, runtime and closure; keep all execution/measurement/scientific flags false. Bind the new controller to the actual newly accepted evidence references. Acceptance must be an owning-root act, not copied historical status.',
   'after_that':'A separately authorized bounded builder may compose and validate the all40 audit plus separate engineering manifest using the unmodified validators. frozen=True is permitted only for an immutable audit-only snapshot with all execution authorizations false. This review creates no graph.',
   'no_source_fix_required_by_this_review':True},
 'separate_unresolved_gates':['Complete production source/native/runtime verification and all41 manifest composition','Independent final B5','Owning-root graph/source/protocol/scope/accounting adoption','Finite preparation release and admission','Fresh measured readiness and external acceptance','Actual loaded controller instance attestation in its separately released worker','Health release and admission','Episode release and admission','Scientific success criteria'],
 'limitations':[
  'Static source proof only. No live controller, physical gain, import-origin receipt or measured readiness was produced.',
  'Source-record file hash and canonical 1116-entry inventory digest were checked; only affected source files were verified against Git. This is not a new full source-record attestation.',
  'Closure file hash, runtime agreement, continuity and relevant deployed modules were checked; not all 6767 external module entries or 3300 runtime file contents were reopened. No whole-closure or graph-completeness claim.',
  'Prior accepted runtime/closure/controller and one-hop proposal lineage were used for continuity only. No recursive historical provenance reconstruction, old readiness reuse, protected-result reads or ledger scans.',
  'No source, state, tree, ledger, frozen protocol, existing artifact or graph edits. New files only under authority output directory.',
  'No GPU, native build, simulation, evaluation, model loading, provider measurement or subagents. No alternate login/provider was used or launched. No credential files were opened; Poe launchers were neither imported nor executed. No prohibited design file was read.',
  'The current official Codex session was used; this report does not independently attest credential/session internals or run a provider/login probe.',
  'Approval/release/readiness fields remain false. PASS_SCOPED_STATIC_BINDINGS is an independent recommendation and grants no authority.'
 ],
 'root_reviewed_created':False,'root_acceptance':False,'b5_review':None,'graph_created':False,'graph_complete':False,'all41_composed':False,'source_adopted':False,'accounting_adopted':False,'fresh_measured_readiness':False,'actual_instance_attested':False,'physical_gain_certified':False,'gpu_authorized':False,'provider_measurement_authorized':False,'finite_preparation_release':False,'health_authorized':False,'episode_authorized':False,'release_enabled':False,'scientific_success':False,'owning_state_mutation':False,
 'stop_check':{'paths':a['stop_authority']['paths'],'all_absent':True,'deadline':a['stop_authority']['deadline']}
}
write('review-v1.json',review)
# Manifest binds all bounded input files and every reviewer-generated artifact;
# external evidence is hashed, not promoted. Manifest excludes itself to avoid cycles.
outputs=[ref(O/n) for n in ['review-v1.json','static-checks-v1.json','source-excerpts-v1.json','adapter-delta-review-v1.json','check-static-v1.py','write-review-v1.py']]
input_map={x['path']:x for x in checks['input_files']};input_map[extra['source']['path']]=extra['source']
write('file-manifest-v1.json',{'schema':'n36-independent-controller-review-file-manifest-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'review':ref(O/'review-v1.json'),'outputs':outputs,'inputs':sorted(input_map.values(),key=lambda x:x['path']),'scope':'Hash identities of bounded review inputs and newly written outputs; no acceptance conveyed to referenced projections. Self hash stored separately.'})
with (O/'file-manifest-v1.sha256').open('x') as f:f.write(ref(O/'file-manifest-v1.json')['sha256']+'  file-manifest-v1.json\n')
print(json.dumps({'status':review['status'],'review':ref(O/'review-v1.json'),'manifest':ref(O/'file-manifest-v1.json')},indent=2))
