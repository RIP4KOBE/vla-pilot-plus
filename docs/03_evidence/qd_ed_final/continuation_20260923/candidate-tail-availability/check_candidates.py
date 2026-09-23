#!/usr/bin/env python3
"""Recorded-only CPU candidate availability check; real reads require root review.

No model, reward/provider, projector, simulator, archive replay or GPU call.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import time

PLAN_SHA = 'ac123471db9fa9468661238982b3bdb5cb1a68010ec8261e0e5b12239c57e7e8'
AUTH_SHA = '6b6d42304f238ed2d88a1689a2ba6becf01761df67c57941b89dc1c26e0a47b6'
MAP_SHA = 'b7ccff3644c4adfa0b2ac3b0b695048f0da97660c46ea1a433491ad8305e49ae'
PROTOCOL_SHA = '981534d1e561dfe888b8cbeac92e4b14ba7fa3ecdaef04d498b7e1760d7f0ff5'
ANALYZER = 'docs/03_evidence/qd_ed_final/continuation_20260923/decision-analysis-draft/analyze_episode.py'
AUDITOR = 'scripts/audit_decision_evidence.py'
ALLOWED_KEYS = {'observed_pairs_t00_c0_20260923', 'observed_pairs_t00_q0_20260923'}


def require(condition, reason):
    if not condition: raise ValueError(reason)


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_ref(ref):
    path = Path(ref['path']).resolve()
    require(sha(path) == ref['sha256'], 'input fingerprint differs: '+str(path))
    return json.loads(path.read_text()), path


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def tensor_identity(value, torch):
    value = value.detach().contiguous()
    require(value.device.type == 'cpu' and bool(torch.isfinite(value).all()), 'nonfinite/nonCPU saved tensor')
    return {'dtype':str(value.dtype), 'shape':list(value.shape),
            'bytes_sha256':hashlib.sha256(value.view(torch.uint8).numpy().tobytes()).hexdigest()}


def summarize_candidates(candidates, selected_fp, selected_quality):
    unknown = [row for row in candidates if row['tail_classification'] is None]
    nonreg = [row for row in candidates if row['tail_classification'] == 'not_flagged_robust_regression']
    quality_preserving = [row for row in nonreg if row['effective_quality'] >= selected_quality]
    distinct_preserving = [row for row in quality_preserving if row['fingerprint'] != selected_fp]
    best = max((row['effective_quality'] for row in nonreg), default=None)
    ties = [row for row in nonreg if row['effective_quality'] == best]
    def exists(rows): return True if rows else None if unknown else False
    return {'canonical_occurrences':len(candidates), 'known_tail_occurrences':len(candidates)-len(unknown),
        'unknown_or_ineligible_occurrences':len(unknown),
        'known_nonflagged_occurrences':len(nonreg), 'any_nonflagged':exists(nonreg),
        'any_nonflagged_quality_ge_selected':exists(quality_preserving),
        'any_distinct_fingerprint_nonflagged_quality_ge_selected':exists(distinct_preserving),
        'best_known_nonflagged_quality':best,
        'best_known_quality_minus_actual_selected':None if best is None else best-selected_quality,
        'maximum_scope':'known_subset_only' if unknown else 'complete_recorded_historical_pool',
        'best_known_exact_ties':[{'occurrence_id':row['occurrence_id'], 'fingerprint':row['fingerprint'],
            'fingerprint_differs_from_selected':row['fingerprint'] != selected_fp,
            'effective_quality':row['effective_quality']} for row in ties],
        'final_time_alternative_availability':'Unknown', 'unexecuted_success':'Unknown'}


def analyze_decision(rows, selected_analysis, target_map, a):
    torch = a.cpu_torch()
    context = a.one(rows, 'decision_context')['values']
    require(context['use_guidance'] is True and selected_analysis['hypothesis_eligible'] is True,
            'only all guided eligible decisions enter candidate comparisons')
    require(selected_analysis['command_translation_matches_projection_source'] is True,
            'command mismatch remains ineligible')
    final = a.one(rows, 'final_selection')
    selected_fp = final['values']['selected_canonical_fingerprint']
    selected_quality = float(final['values']['selected_quality'])
    require(math.isfinite(selected_quality), 'selected quality is nonfinite')
    require(selected_fp == a.one(rows,'policy_action_decode')['values']['selected_canonical_fingerprint'],
            'actual selected fingerprint differs')
    lookup = {row['sequence']:row for row in rows}
    scores = [row for row in rows if row['event']=='scoring_inputs' and
              row['values']['scoring_scope']['role'].startswith('canonical_') and row['sequence'] < final['sequence']]
    candidates = []
    for batch in (row for row in rows if row['event']=='canonical_candidate_batch'):
        require(batch['sequence'] < final['sequence'], 'post-selection candidate is not predecision evidence')
        value = batch['values']
        matches = []
        for score in scores:
            scored = score['values']
            if (score['sequence'] >= batch['sequence'] or scored['scoring_scope']['iter_idx'] != value['iter_idx']
                    or scored['samples'].shape != value['candidates'].shape
                    or scored['samples'].dtype != value['candidates'].dtype
                    or not torch.equal(scored['samples'],value['candidates'])):
                continue
            effective = a.one([row for row in rows if row['event']=='effective_quality'
                and row['values']['scoring_batch_id']==score['sequence']], 'effective_quality')['values']
            if (effective['quality'].shape == value['effective_quality'].shape
                    and effective['quality'].dtype == value['effective_quality'].dtype
                    and torch.equal(effective['quality'],value['effective_quality'])):
                matches.append((score,effective))
        for index, sample in enumerate(value['candidates']):
            fp = a.fingerprint(sample)
            require(fp == value['canonical_fingerprints'][index], 'canonical fingerprint differs')
            item = {'occurrence_id':value['occurrence_ids'][index], 'fingerprint':fp,
                'canonical_batch_sequence':batch['sequence'], 'candidate_row':index, 'iteration':value['iter_idx'],
                'effective_quality':float(value['effective_quality'][index]), 'quality_dtype':str(value['effective_quality'].dtype),
                'tail_classification':None, 'unknown_reasons':[], 'ineligible_reasons':[],
                'final_time_availability':'Unknown'}
            require(math.isfinite(item['effective_quality']), 'recorded candidate quality is nonfinite')
            if len(matches) != 1:
                item['unknown_reasons'].append('canonical_to_scoring_batch_match_missing_or_ambiguous')
                candidates.append(item)
                continue
            score,effective = matches[0]
            scored = score['values']
            item.update(scoring_batch_sequence=score['sequence'], scoring_scope=scored['scoring_scope'], reward_mode=effective['reward_mode'])
            projection = scored['projected_xyz'][index]
            origin = lookup[scored['projection_origin_sequences'][index]]['values']['source_eef_position']
            item['recorded_value_identity'] = {name:tensor_identity(tensor,torch) for name,tensor in {
                'projection':projection,'provider_input':scored['provider_input_xyz'][index],
                'source_eef':origin,'keypoints':scored['keypoints']}.items()}
            item['native_source_eef'] = a.plain(origin)
            if effective['reward_mode'] != 'normal': item['ineligible_reasons'].append('reward_mode_not_normal')
            if scored['slice_kind'] != 'eds' or tuple(projection.shape)!=(9,3) or not torch.equal(scored['provider_input_xyz'][index],projection[1:8]):
                item['ineligible_reasons'].append('provider_slice_not_original_t1_through_t7')
            target,_,reason = a.resolve_target(context,{'keypoints':scored['keypoints']},target_map)
            if target is None or target != selected_analysis['frozen_target']:
                item['ineligible_reasons'].append(reason or 'target_differs_from_selected_frozen_target')
            if not item['ineligible_reasons']:
                d7,d8 = a.distance(a.plain(projection[7]),target),a.distance(a.plain(projection[8]),target)
                floor = a.ulp_norm(projection[7])+a.ulp_norm(projection[8])
                item.update(frozen_target=target, projected_distance7_m=d7, projected_distance8_m=d8,
                    projected_tail_delta_m=d8-d7, projected_native_ulp_floor_m=floor,
                    tail_classification='robust_regression' if d8-d7>floor else 'not_flagged_robust_regression')
            candidates.append(item)
    require(bool(candidates), 'canonical historical pool empty')
    require(len({row['occurrence_id'] for row in candidates})==len(candidates), 'duplicate occurrence ID')
    groups=defaultdict(list)
    for row in candidates: groups[row['fingerprint']].append(row)
    ambiguous=[]
    for fp,group in groups.items():
        values={json.dumps(row.get('recorded_value_identity'),sort_keys=True) for row in group}
        if len(group)>1 and (len(values)>1 or 'null' in values):
            ambiguous.append(fp)
            for row in group:
                row['tail_classification']=None
                row['unknown_reasons'].append('same_fingerprint_projection_origin_or_keypoints_ambiguous')
    return {'decision_id':selected_analysis['decision_id'], 'global_step':selected_analysis['global_step'],
        'stage':selected_analysis['stage'], 'guidance':True, 'selected_fingerprint':selected_fp,
        'actual_selected_quality':selected_quality,
        'original_actual_A':None if selected_analysis['diagnostics']['step7_to8'] is None else selected_analysis['diagnostics']['step7_to8']['both_regress_robust'],
        'original_actual_B':selected_analysis['diagnostics']['projection_optimism_witness'],
        'ambiguous_fingerprints':ambiguous,'candidates':candidates,
        'summary':summarize_candidates(candidates,selected_fp,selected_quality)}


def analyze_events(events, analysis, target_map, a):
    grouped=defaultdict(list)
    for row in events: grouped[row['decision_id']].append(row)
    require(set(grouped)=={row['decision_id'] for row in analysis['decisions']}, 'decision universe differs')
    results,excluded=[],[]
    for decision in analysis['decisions']:
        if decision['guidance'] and decision['hypothesis_eligible']:
            results.append(analyze_decision(grouped[decision['decision_id']],decision,target_map,a))
        else:
            excluded.append({'decision_id':decision['decision_id'],'guidance':decision['guidance'],
                'hypothesis_eligible':decision['hypothesis_eligible'],'unknown_reasons':decision['unknown_reasons'],
                'ineligible_reasons':decision['hypothesis_ineligible_reasons']})
    return {'schema':'qd-ed-recorded-candidate-tail-availability-v1','decisions':results,'excluded_decisions':excluded,
        'scope':'All guided eligible decisions, not selected by A/B witness; canonical historical scored pool only.',
        'eligible_decisions':len(results),'excluded_decision_count':len(excluded),
        'descriptive_decision_counts':dict(Counter('alternative_exists' if row['summary']['any_nonflagged'] is True else
            'no_known_alternative' if row['summary']['any_nonflagged'] is False else 'Unknown' for row in results)),
        'promotion_status':'NOT_EVALUATED','statistical_unit':'Episode; decisions are correlated descriptions, not independent trials.',
        'final_time_alternative_availability':'Unknown','counterfactual_success':'Unknown'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True,type=Path)
    parser.add_argument('--output-dir',required=True,type=Path)
    parser.add_argument('--execute-reviewed',action='store_true',help='Use only after root reviewed script/protocol and authorized actual bundle reads')
    args=parser.parse_args()
    require(args.execute_reviewed,'actual bundle reads require root review and explicit execution flag')
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','explicit empty CUDA_VISIBLE_DEVICES required')
    manifest=json.loads(args.manifest.read_text())
    require(manifest['schema']=='qd-ed-candidate-tail-input-v1','manifest schema differs')
    require(manifest['script_sha256']==sha(__file__) and manifest['protocol_sha256']==PROTOCOL_SHA==sha(Path(__file__).with_name('protocol.md')),
            'script/protocol was not frozen before bundle reads')
    require(manifest['plan']['sha256']==PLAN_SHA and manifest['authorization']['sha256']==AUTH_SHA and
            manifest['target_map']['sha256']==MAP_SHA,'plan/authorized supplemental identity condition differs')
    plan,_=read_ref(manifest['plan']); authorization,_=read_ref(manifest['authorization'])
    _,map_path=read_ref(manifest['target_map'])
    terminal,terminal_path=read_ref(manifest['terminal']); saved_audit,_=read_ref(manifest['audit'])
    analysis,_=read_ref(manifest['supplemental_analysis'])
    require(terminal['episode_key'] in ALLOWED_KEYS and terminal['identity']['task_id']==0 and terminal['physical_gpu']==3,
            'only completed task0 C0/Q0 GPU3 episodes are authorized')
    row=next(row for row in plan['episodes'] if row['episode_key']==terminal['episode_key'])
    require(terminal['identity']=={key:row[key] for key in ('split','iteration','profile','task_id','env_seed','policy_seed','init_index')}
        and terminal['plan_sha256']==PLAN_SHA and terminal['event']=='valid' and terminal['outcome_valid'] is True,
        'terminal plan/identity/completion differs')
    require(terminal['source_commit']==plan['source_commit'] and terminal['profile_manifest_sha256']==plan['profiles_sha256'] and
        terminal['runtime_inventory_sha256']==plan['runtime_inventory_sha256'] and terminal['runtime_manifest_sha256']==plan['runtime_manifest_sha256'],
        'terminal frozen source/runtime/profile differs')
    output=terminal_path.parent
    require(output==Path(terminal['output_dir']).resolve() and terminal_path.name=='attempt-result.json','terminal output differs')
    episode=output/'eds_eval/decision_evidence/episode_000'; compute=output/'eds_eval/episode_compute.jsonl'
    require(analysis['schema']=='qd-ed-selected-decision-analysis-v2' and analysis['input_kind']=='audited_runtime_episode' and analysis['task_id']==0 and
        analysis['episode_seed']==row['env_seed'] and analysis['episode_dir']==str(episode) and
        analysis['input_sha256'].get(str(map_path))==MAP_SHA,'supplemental analysis identity differs')
    require(saved_audit['accepted'] is True and saved_audit['evidence_complete'] is True and
        analysis['audit']['accepted'] is True and analysis['audit']['evidence_complete'] is True,'complete accepted audits required')
    require(saved_audit['episode_dir']==str(episode) and saved_audit['episode_compute_file']==str(compute) and
        analysis['audit']=={key:value for key,value in saved_audit.items() if key!='wrapper_observation'} and
        analysis['cuda_initialized_before'] is False and analysis['cuda_initialized_after'] is False,
        'audit/CPU analysis linkage differs')
    root=Path(plan['worktree']).resolve(); sources={row['path']:row['sha256'] for row in plan['code_files']}
    require(analysis['source_sha256']=={'analysis':sources[ANALYZER],'existing_auditor':sources[AUDITOR]} and
        sha(root/ANALYZER)==sources[ANALYZER] and sha(root/AUDITOR)==sources[AUDITOR],'frozen analyzer/auditor source differs')
    destination=args.output_dir.resolve()
    require(destination.is_relative_to(Path(plan['artifact_root']).resolve()/'continuation_20260923') and
        not destination.exists() and not destination.is_relative_to(output),'new artifact output directory required')
    a=module('frozen_candidate_analysis_helpers',root/ANALYZER)
    audit=module('frozen_candidate_auditor',root/AUDITOR)
    torch=a.cpu_torch(); started=time.monotonic(); peak_before=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    target_map,map_hashes=a.load_target_map(map_path)
    for path,expected in analysis['input_sha256'].items():
        resolved=Path(path).resolve()
        require(resolved.is_relative_to(episode) or resolved==compute or str(resolved) in map_hashes,
                'analysis input escapes this task0 episode/reviewed map sources')
        require(sha(path)==expected,'supplemental input changed: '+path)
    fresh=audit.audit_episode(episode,compute)
    require(fresh['accepted'] is True and fresh['evidence_complete'] is True,'fresh complete audit refused')
    require(fresh==analysis['audit'],'fresh audit differs from supplemental evidence')
    events=audit.load_events(episode,json.loads((episode/'status.json').read_text()))
    report=analyze_events(events,analysis,target_map,a)
    require(not torch.cuda.is_initialized(),'unexpected CUDA initialization')
    for path,expected in {**analysis['input_sha256'],**map_hashes}.items(): require(sha(path)==expected,'input changed while reading')
    report.update(episode_key=terminal['episode_key'],attempt_id=terminal['attempt_id'],original_success=terminal['success'],
        source_sha256=analysis['source_sha256'],input_manifest=manifest,authorization_condition='post_data_identity_v3',
        cuda_initialized=False,CPU_wall_seconds=time.monotonic()-started,
        parent_ru_maxrss_before_kib=peak_before,parent_ru_maxrss_after_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        memory_scope='Cumulative parent process peaks including imports/audit; differences are not exclusive memory usage.')
    destination.mkdir(parents=True,exist_ok=False)
    (destination/'candidate-tail-availability.json').write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps({'output_dir':str(destination),'eligible_decisions':report['eligible_decisions'],
        'excluded_decisions':report['excluded_decision_count'],'promotion_status':'NOT_EVALUATED'}))


if __name__=='__main__': main()
