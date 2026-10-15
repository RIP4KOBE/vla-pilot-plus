import pathlib,json,hashlib,datetime
O=pathlib.Path(__file__).resolve().parent
R=json.loads((O/'replay-results-v5.json').read_text())
assert not R['errors'] and len(R['rows'])==6
assert all(c['stored_projection_provider_quality_exact'] and c['sequential_projection_exact'] and c['sequential_quality_exact'] and c['sequential_descriptor_exact'] for r in R['rows'] for c in r['control_replay'])
assert all(r['native_reference']['archive_control_matches_recorded_update'] for r in R['rows'])
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
artifacts=[ref(O/n) for n in ['replay-v1.py','replay-results-v1.json','replay-v1.log','replay-v2.py','replay-results-v2.json','replay-v2.log','arithmetic-diagnostic-v1.py','arithmetic-diagnostic-results-v1.json','replay-v3.py','replay-results-v3.json','replay-v3.log','replay-v4.py','replay-results-v4.json','replay-v4.log','replay-v5.py','replay-results-v5.json','replay-v5.log','write-report-v1.py']]
rows=[]
for r in R['rows']:
 n=r['native_reference'];vals={c['name']:c for c in n['comparisons']}
 assert vals['direct']['quality']==r['recorded_direct_quality']
 assert vals['template']['quality']==r['recorded_template_quality']
 rows.append({'attempt_id':r['attempt_id'],'current_step':r['step'],'decision_id':r['decision_id'],
              'registered_opportunity_iteration':0,'native_dtype':r['native_dtype'],
              'comparisons':n,'recorded_direct_quality':r['recorded_direct_quality'],
              'recorded_template_quality':r['recorded_template_quality'],'clipped_components_per_two_halves':r['clipped_components'],
              'control_replay':r['control_replay'],'config':r['config']})
limitations=[
 'Six preselected, overlapping Dev next-decision packets only: task 0 steps 696/704/712 and task 6 steps 568/576/584. These are not six independent trials or a population survival-rate estimate. The ineligible seventh window was not scored.',
 'Only the first registered opportunity (iteration 0, slot 15) per packet was tested, matching feasibility.py template selection. Existing bound bundles were deserialized and filtered by the six step identities; no additional historical artifact search or protected evaluation was performed.',
 'Native reference detour scores are new CPU calculations, not recorded deployed N36 scores. Historical CUDA binary/build provenance is not attested by these packets. The installed PyTorch 2.7.1+cu126 ScanUtils.cuh supports the scalar_t sequential outer-dimension accumulation model; 192/192 recorded controls match projections, provider scores and descriptors exactly under that model. This validates the bounded reference, not every unseen input or an adopted runtime implementation.',
 'Ordinary torch CPU cumsum is not bitwise equivalent to the recorded projection: all 12 full control batches disagree somewhere. Its scores and one-update simulations are retained as superseded diagnostics, not asserted as exact deployed scores. No float32-only or binary64 proxy score is substituted for native scoring.',
 'The one-update comparison preserves the recorded initial archive and the 15 ordinary first offspring, replaces slot 15 with the registered detour, and uses the unchanged QDArchive implementation. Holding these first offspring fixed is justified by insertion after their rollout. Holding subsequent offspring fixed would not be justified: changed archive elites/visits/parent allocations can change denoising and subsequent competition.',
 'No counterfactual later-round populations, N36 final archive, selected/decoded/acknowledged detour, physical response, capture entry, or fresh matched task outcomes exist in this review. Prospective archive survival and execution remain UNKNOWN. A direct-approach candidate appearing in the same cell at any later update would strictly beat the detour in all six matched comparisons.',
 'No N36 implementation was adopted or audited end-to-end. The decision-level duration of proposal eligibility must ultimately follow its registered lifecycle; this report neither changes that lifecycle nor assumes a direct competitor is forcibly retained or forcibly excluded.',
 'Authority SHA-256 was computed locally; no externally supplied digest for authority-v1.json itself was available. Its supplied reference digests, ledger prefix length/hash, packet hashes, provider source hashes and relevant owning-source blobs were verified. Prior root conclusions were not used as independent scoring evidence.',
 'CPU activity and this PASS do not establish collision avoidance, task success, scientific promotion, GPU authorization, protected-phase release, or implementation adoption.'
]
findings=[
 'Credible ordinary-selection feasibility exists in the three task-0 first-update counterfactuals: the detour replaces the proposal slot, is retained in its cell, and is archive global best immediately after that update. Task-6 detours are rejected in all three first updates. This mixed result supports bounded plausibility, not universal selectability.',
 'Direct approach strictly out-scores the registered detour in all six packets; all six share their direct comparator cell and none is a score tie. Fingerprint tie-breaking cannot rescue a lower-quality detour if direct approach coexists in that cell.',
 'Direct approach is a matched alternative in slot 15, not an extra mandatory seventeenth competitor. Comparing only detour versus direct would incorrectly prove universal rejection. The first ordinary other-15 and incumbents are weaker than the task-0 detour, even though direct approach would be stronger.',
 'The provider is the hash-bound stage1_guidance complete weighted-distance template with target index 0 and loader wrapper. EDS slices projected trajectory indices 1:8, so only positions after actions 1 through 7 are scored; weights are [1,1,1,1,3,3,3]/13. The eighth endpoint affects the target-relative XY cell descriptor but is excluded from this provider score.',
 'Scoring uses native bf16 actions and scoring keypoints, native projection origin cast, native multiplication by 0.01 and native cumulative/position additions. Provider norm and square retain native arithmetic; scalar-created weights are float32 and the final aggregate is cast back to native bf16. Raw observation geometry remains binary64 for the registered proposal before a single bf16 command cast.',
 'Guidance projection reads native action channels directly and does not apply actuator clipping; the registered proposal itself clips each translation component before encoding. Existing template actions were not retrospectively clipped. Task-6 clipping and native accumulation produce endpoint z differences versus direct of +0.00048828125, +0.000244140625, and -0.00048828125 m; XY descriptors still coincide. Task-0 native endpoints coincide in these packets. No endpoint-cancellation assumption was used to infer quality.',
 'Archive capacity is one per 4x4 cell, fixed-initial bounds with edge clamping, no secondary lane, sparse-priority parent allocation and no global-quality anchor. Per-cell batch winners and replacements use descending quality then ascending canonical action fingerprint; global final selection uses descending quality, fingerprint, then cell. Fingerprints cover the entire 64x128 action after canonical little-endian float32 conversion, including unchanged remainder.',
 'Provider replay on stored projections matches all 192 control scores. A CPU model of the installed CUDA outer-dimension scan reproduces all 192 recorded projected trajectories, scores and descriptors exactly. Six actual initial-plus-first-offspring archive update controls match their recorded quality/fingerprint maps. The naive CPU discrepancy and the initial script exception are preserved.'
]
report={
 'schema':'n36-independent-cpu-selection-feasibility-review-v1',
 'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'node_id':'15.6','proposal':'N36 registered tangent detour','source':R['source'],
 'reviewer_role':'independent CPU scientific feasibility reviewer; not coordinator; no further delegation',
 'status':'PASS',
 'verdict_scope':'Bounded ordinary-selection plausibility only. Three task-0 first-update counterfactuals provide a credible route through unchanged selection; actual prospective archive survival is UNKNOWN.',
 'decision_basis':'PASS requires credible ordinary-selection feasibility in at least one of the already-bound eligible packets, not proof of future selection or task success. The score penalty relative to direct approach does not universally prohibit insertion because direct occupies the replacement slot in the matched control.',
 'authority':ref(O/'authority-v1.json'),
 'exactness':{'recorded_provider_scores_reproduced':192,'recorded_native_projection_scores_descriptors_reproduced_under_source_backed_cuda_scan_reference':192,'recorded_archive_update_controls_reproduced':6,'unmodified_cpu_cumsum_batch_exact_matches':0,'unmodified_cpu_cumsum_control_batches':12,'exact_deployed_n36_detour_scores_observed':False,'cpu_native_reference_scores_reconstructed':True,'reference_kernel_model':'CUDA outer-dimension scalar_t sequential accumulation; installed header inspected and hashed','historical_cuda_binary_attested':False},
 'findings':findings,'comparisons':rows,'limitations_and_missing_evidence':limitations,
 'source_and_input_hashes':R['hash_manifest'],'analysis_artifacts':artifacts,
 'operational_errors':[{'artifact':ref(O/'replay-results-v1.json'),'error':json.loads((O/'replay-results-v1.json').read_text())['errors'][0],'resolution':'Analysis script v2 supplies QDBounds checksum metadata; no owning-source change. Later checks use recorded bounds and exact archive quality/fingerprint control comparisons.'},
 {'kind':'native_CPU_projection_control_mismatch','preserved_in':[ref(O/'replay-results-v2.json'),ref(O/'arithmetic-diagnostic-results-v1.json')],'resolution':'Separated native CPU diagnostics from source-backed CUDA-scan CPU reference; latter control-matches all 192 rows. No mismatch suppressed.'}],
 'compliance':{'cuda_visible_devices':'','torch_threads':1,'omp_mkl_openblas_threads':1,'torch_version':R['torch_version'],'gpu_used':False,'simulator_episodes':0,'source_edits':False,'commits':False,'worktree_created':False,'state_ledger_tree_mutation':False,'resource_reservations':False,'protected_validation_formal_access':False,'external_messages':False,'further_delegation':False,'forbidden_design_file_read':False,'credentials_or_alternate_provider_access':False,'superpowers_used':False,'outputs_only_in_authorized_directory':True},
 'gpu_authorized':False,'implementation_adoption_authorized':False,'promotion':False,'target_met':False,'prospective_archive_survival':'UNKNOWN'
}
(O/'report-v1.json').write_text(json.dumps(report,indent=2)+'\n')
lines=[
 '**PASS — bounded ordinary-selection plausibility only.** The registered detour has a credible route through unchanged selection in the three task-0 packets. The three task-6 detours fail the first archive update. Actual prospective archive survival is **UNKNOWN**. This review authorizes neither GPU work nor implementation adoption and is not task success or scientific promotion.',
 '',
 f"Frozen owning source: `{R['source']}`. Authority SHA-256: `{report['authority']['sha256']}`. All supplied direct reference hashes, the specified ledger prefix, bound packet files, provider text and inspected owning-source blobs matched. The authority itself had no externally supplied expected digest. Source/input/script hashes and complete numeric details are in [report-v1.json](report-v1.json) and [replay-results-v5.json](replay-results-v5.json).",
 '',
 'The review independently inspected source and replayed only the six eligible next-decision packets: task 0 at 696/704/712 and task 6 at 568/576/584. It uses each first opportunity (iteration 0, slot 15), the same template selected by feasibility.py, and the exact registered detour arithmetic with clipping followed by one native bf16 cast. Direct proposals were regenerated with frozen N34 code and matched the recorded candidate bytes. No trigger/encoding gate or broad N35 diagnosis was repeated.',
 '',
 '**Scoring semantics and native arithmetic.** The hash-bound provider scores negative weighted squared Euclidean target distance. EDS passes trajectory indices `1:8`: positions after actions 1–7, with weights `[1,1,1,1,3,3,3]/13`. The eighth endpoint is excluded from quality but determines the target-relative XY descriptor. Native bf16 scoring keypoints differ from the raw binary64 geometry packet. The projection uses native action channels, a cast origin, multiplication by 0.01, cumulative sums and position addition. It performs no actuator clipping; only the registered proposal commands are clipped before encoding. The loader wrapper leaves scalar-created weights in float32, then the frozen scorer casts the aggregate back to bf16.',
 '',
 'Unmodified CPU execution of the frozen projection failed exact control comparison in all 12 batches (maximum batch quality differences from 0.0000152587890625 to 0.00006103515625). The source dependency `torch/include/ATen/native/cuda/ScanUtils.cuh`, lines 270–283 and 446–471, selects sequential `scalar_t` accumulation for this 8x3, dim-0 scan. A CPU reference using that accumulation reproduced **192/192 recorded projections, provider scores and descriptors**. The unchanged provider also reproduced 192/192 scores when given stored projections. All six recorded archive-update control maps matched.',
 '',
 'The following are exact bf16-representable **CPU native-reference values under that source-backed accumulation model**. Direct and template values additionally equal the recorded qualities. Detour values are reconstructed, not observed N36 runtime scores. The packets do not attest the historical CUDA binary; no claim of newly measured deployed detour scores is made.',
 '',
 '| Task / step | Detour reference | Direct (also recorded) | Template (also recorded) | Detour − direct | Detour − template |',
 '|---|---:|---:|---:|---:|---:|'
]
for r in rows:
 n=r['comparisons'];d={x['name']:x['quality'] for x in n['comparisons']};task=0 if 't00' in r['attempt_id'] else 6
 lines.append(f"| {task} / {r['current_step']} | {d['detour']!r} | {d['direct']!r} | {d['template']!r} | {n['detour_minus_direct']!r} | {n['detour_minus_template']!r} |")
lines += ['',
 'Detour and direct occupy the same cell in every packet, with strictly different qualities: no native score tie rescues the detour. In task 0, native endpoints coincide. Task-6 endpoint z differences are +0.00048828125, +0.000244140625 and −0.00048828125 m; their XY descriptors still coincide. Clipping and native arithmetic were applied explicitly rather than assuming exact tangent cancellation.',
 '',
 '**Ordinary archive competition.** The frozen archive keeps one elite per 4x4 cell. It chooses the higher quality, then the lexicographically smaller full-action fingerprint on ties. Final selection uses highest archive quality, then fingerprint, then cell. Fingerprints hash the entire action after canonical little-endian float32 conversion. Fixed-initial bounds, edge clamping, sparse-priority parent sampling, no secondary lane and no global-quality anchor remain unchanged.',
 '',
 'The direct approach is the matched alternative in the replacement slot; it is not a mandatory extra competitor. Each conditional update preserves the recorded initial archive and all 15 ordinary offspring, replaces slot 15 with the detour, then calls the unchanged QDArchive implementation. This preserves the first offspring because insertion follows their rollout. It does not freeze later offspring or force selection.',
 '',
 '| Task / step | Detour cell | Margin over best same-cell incumbent/ordinary offspring | Retained after first update | Global best after first update |',
 '|---|---:|---:|---|---|'
]
for r in rows:
 n=r['comparisons'];task=0 if 't00' in r['attempt_id'] else 6
 lines.append(f"| {task} / {r['current_step']} | {n['comparisons'][0]['cell_id']} | {n['margin_over_samecell_competitor']!r} | {'Yes' if n['one_update_retained'] else 'No'} | {'Yes' if n['one_update_global_best'] else 'No'} |")
lines += ['',
 'The three positive task-0 margins establish credible initial selection plausibility despite the direct-approach penalty. The task-6 failures show that an improvement over the template alone is insufficient: at step 568, the detour beats its template but still loses to an ordinary offspring in its cell. If direct approach is present in the same cell at any update, it strictly beats the matched detour in all six packets.',
 '',
 '**Limits and missing evidence.** These are three overlapping packets from each of two tasks, not six independent experiments or an estimate of survival probability. The result covers the first insertion only. Changed archive contents can change future parent allocation and denoising, so recorded later rounds cannot establish a counterfactual N36 final archive. Missing evidence is the actual later N36 populations/archives and final selection, runtime scoring of the new candidate on an attested backend, selected/decode/acknowledgement linkage, physical response, actual capture entry and fresh matched task outcomes. None was fabricated or requested through prohibited work. The registered lifecycle and hypothesis were not revised.',
 '',
 'The historical CUDA binary is not hash-attested here. Source inspection plus all 192 exact controls supports a bounded native-reference calculation; it does not certify bitwise behavior on every unseen candidate or an implementation that has not been adopted. Consequently this PASS is for scientific plausibility of ordinary selection, not a completed prospective survival audit.',
 '',
 '**Preserved failures and audit trail.** [replay-v1.log](replay-v1.log) retains the initial `QDBounds` missing-checksum exception. Version 2 fixed that analysis-only constructor use and exposed the CPU/backend discrepancy. [arithmetic-diagnostic-results-v1.json](arithmetic-diagnostic-results-v1.json) and replay versions 2–4 preserve the intermediate arithmetic evidence; their default-CPU scores are superseded by the explicitly labeled native-reference comparisons. [replay-v5.py](replay-v5.py) is the final bounded script; all artifacts and source dependencies are hashed in the JSON report. The existing prior root failure records were left untouched; this review made no delegation attempt.',
 '',
 'All analysis ran on CPU with `CUDA_VISIBLE_DEVICES=""`, Torch intra/inter-op threads 1 and OMP/MKL/OpenBLAS threads 1. No source edits, commits, worktrees, state/ledger/tree changes, resource reservations, simulator episodes, protected data, external messages, credentials, alternate providers or forbidden design document were used. All created files are confined to the authorized selection-review directory. No GPU release, implementation adoption or promotion follows from this PASS.'
]
(O/'report-v1.md').write_text('\n'.join(lines)+'\n')
(O/'report-checksums-v1.json').write_text(json.dumps({'report':ref(O/'report-v1.json'),'markdown':ref(O/'report-v1.md'),'writer':ref(__file__)},indent=2)+'\n')
print(json.dumps({'status':report['status'],'reports':[ref(O/'report-v1.json'),ref(O/'report-v1.md')],'comparisons':len(rows),'controls':192},indent=2))
