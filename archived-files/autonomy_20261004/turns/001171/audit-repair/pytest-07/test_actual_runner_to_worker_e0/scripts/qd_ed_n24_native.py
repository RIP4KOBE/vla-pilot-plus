"""Profile-bound CPU consumption of the metered independent native report."""
import json
import math
from pathlib import Path

ARMS = ('C0', 'Q0', 'N23', 'N24')
MODE = 'canonical_full_close_v1'
CLIP = ('score_batches_verified','candidate_scores_verified','clipped_prefix_candidates','rank_changed_batches')
AUX = ('qd_actuator_overhead_seconds','qd_actuator_quality_batches','qd_actuator_quality_candidates','qd_actuator_clipped_prefix_candidates')


def require(ok, message):
    if not ok: raise ValueError('N24 native: ' + message)


def counts(profile, metrics, report, guided_count=None):
    require(profile in ARMS and report.get('accepted') is True and report.get('evidence_complete') is True,
            'unknown profile or incomplete native audit')
    n=len(metrics)
    observed=report.get('observed_counts');require(isinstance(observed,dict),'native counts unknown')
    canonical=observed.get('canonical_candidate_batch',0)  # Persisted Counter omits exactly zero kinds.
    require(type(canonical) is int and canonical==11*n,'canonical/metric denominator differs')
    if guided_count is not None:require(type(guided_count) is int and guided_count==n,'guided denominator differs')
    result={'guided_decisions':n,'parent_rounds_verified':0}
    auxiliary={}
    require(all(m.get('score_call_count')==11 and m.get('search_evaluation_count')==176
                and all(m.get(k)==10 for k in ('resample_count','renoise_count','rollout_count')) for m in metrics),
            'fixed compute differs')
    if profile in ('C0','Q0'):
        require(all(m.get('qd_quality_mode','provider')=='provider'
            and m.get('qd_gripper_rescue_mode','none')=='none'
            and m.get('qd_archive_active_for_chunk') is (profile=='Q0') for m in metrics), 'legacy control differs')
        require(not report.get('n24_gripper_parent_rescue_audit') and not report.get('n23_actuator_clipped_quality_audit'),
                'control has non-default native evidence')
        return result,auxiliary
    selection=report.get('n5_grasp_timing_audit',{})
    clip=report.get('n23_actuator_clipped_quality_audit',{})
    rescue=report.get('n24_gripper_parent_rescue_audit',{})
    if n==0:
        require(not selection and not clip and not rescue,'unguided evidence differs')
        return result,auxiliary
    require(selection.get('checked_decisions')==n and selection.get('parent_rounds_verified')==10*n
        and selection.get('canonical_batches_verified')==11*n and selection.get('canonical_candidates_verified')==176*n,
        'substantive parent/terminal evidence differs')
    require(all(m.get('qd_archive_active_for_chunk') is True and m.get('qd_quality_mode')=='actuator_clipped_provider_v1'
        and m.get('qd_descriptor')=='target_xy_quadrant_signed_height_v1'
        and m.get('qd_final_selection_mode')=='terminal_grasp_proximity_v1' for m in metrics), 'non-default mode missing')
    require(clip.get('score_batches_verified')==11*n and clip.get('candidate_scores_verified')==176*n,'clip count differs')
    for k in CLIP:
        require(type(clip.get(k)) is int and clip[k]>=0,'missing clipping counter');result[k]=clip[k]
    result['parent_rounds_verified']=10*n
    for k in AUX:
        values=[m.get(k) for m in metrics]
        require(all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in values),'missing auxiliary cost')
        auxiliary[k]=sum(values)
    require(auxiliary['qd_actuator_quality_batches']==11*n and auxiliary['qd_actuator_quality_candidates']==176*n
        and auxiliary['qd_actuator_clipped_prefix_candidates']==clip['clipped_prefix_candidates'],'serialized clipping counters differ')
    if profile=='N23':
        require(not rescue and all(m.get('qd_gripper_rescue_mode','none')=='none' for m in metrics),'N23 rescue activation')
        return result,auxiliary
    require(rescue.get('schema')=='n24-native-gripper-parent-rescue-audit-v1'
        and rescue.get('checked_decisions')==n and rescue.get('parent_rounds_verified')==10*n
        and rescue.get('canonical_batches_verified')==11*n and rescue.get('canonical_candidates_verified')==176*n,
        'required N24 gate missing, incomplete or downgraded')
    require(all(m.get('qd_gripper_rescue_mode')==MODE and m.get('qd_gripper_rescue_checks')==176 for m in metrics),
            'N24 mode/checks missing')
    for field,native in (('qd_gripper_rescue_updates','cache_updates'),('qd_gripper_rescue_substitutions','substitutions')):
        values=[m.get(field) for m in metrics]
        require(all(type(v) is int and v>=0 for v in values) and sum(values)==rescue.get(native),'N24 native counter differs')
        result[native]=sum(values)
    for m in metrics:
        substitutions=m['qd_gripper_rescue_substitutions'];source=m.get('parent_count_by_source',{})
        require(0<=substitutions<=10 and source.get('qd_archive_offspring')==160-substitutions
            and source.get('qd_gripper_rescue_offspring',0)==substitutions
            and sum(source.values())==160,'actual parent source counts differ')
        slots=m.get('qd_parent_slots_by_cell_by_iter',[])
        require(len(slots)==10 and all(sum(v.values())==16 for v in slots),'original archive allocation counts missing')
        cells=m.get('qd_gripper_rescue_actual_cells_by_iter',[])
        require(len(cells)==10 and all(len(v)==16 and all(type(c) is int and 0<=c<16 for c in v) for v in cells),
                'actual cell telemetry missing')
        latency=m.get('qd_gripper_rescue_overhead_seconds')
        require(type(latency) in (int,float) and math.isfinite(latency) and latency>=0,'rescue auxiliary cost missing')
    auxiliary['qd_gripper_rescue_overhead_seconds']=sum(m['qd_gripper_rescue_overhead_seconds'] for m in metrics)
    return result,auxiliary


def from_output(profile, output, report, guided_count=None):
    path=Path(output)/'eds_eval/eds_metrics.jsonl'
    require(not path.is_symlink() and (path.is_file() or not path.exists()),'metrics unsafe')
    metrics=[json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.is_file() else []
    compute_path=Path(output)/'eds_eval/episode_compute.jsonl'
    require(not compute_path.is_symlink() and compute_path.is_file(),'episode compute missing or unsafe')
    compute=[json.loads(line) for line in compute_path.read_text().splitlines() if line.strip()]
    require(len(compute)==1 and compute[0].get('policy_counters_available') is True
        and type(compute[0].get('guided_chunks')) is int and compute[0]['guided_chunks']==len(metrics),
        'independent episode guided denominator differs')
    return counts(profile,metrics,report,compute[0]['guided_chunks'] if guided_count is None else guided_count)
