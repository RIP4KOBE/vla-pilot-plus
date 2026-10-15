"""External operational adapter for N7's frozen legacy metrics serializer.

This is not a provider fallback. Only an omitted provider-mode metric is
interpreted, after exact frozen profile and independently audited raw evidence.
Original metrics/native files remain immutable.
"""
import math
from pathlib import Path

N7_PROFILE_SHA='d77b8472364cd00dc2548e9e8160672a4f16335a56736cf66d77de6ae74ccb2d'


def verify_provider_profile(plan,manifest,root,w):
    path=Path(root)/'configs/qd_ed_final/candidate_n7.json'
    expected={'path':str(path),'sha256':N7_PROFILE_SHA}
    w.require(plan['candidate_profiles'].get('N7')==expected and w.sha(path)==N7_PROFILE_SHA,
        'N7 omitted mode requires exact frozen profile')
    profile=manifest['profiles']['N7']['resolved_eds_config']
    w.require(profile.get('qd_quality_mode','provider')=='provider'
        and profile.get('qd_descriptor')=='target_xy_quadrant_signed_height_v1'
        and profile.get('qd_final_selection_mode')=='terminal_grasp_proximity_v1',
        'N7 omitted mode incompatible with frozen resolved profile')


def raw_provider_evidence(report,n,w):
    w.require(report.get('accepted') is True and report.get('evidence_complete') is True,
        'N7 omitted mode requires accepted complete native evidence')
    gate=report.get('n5_grasp_timing_audit',{})
    w.require(gate.get('schema')=='n5-native-grasp-timing-audit-v1'
        and gate.get('checked_decisions')==n and gate.get('parent_rounds_verified')==10*n
        and gate.get('canonical_batches_verified')==11*n and gate.get('canonical_candidates_verified')==176*n
        and len(gate.get('decisions',[]))==n,'N7 omitted mode native parent/canonical coverage differs')
    w.require(not any(report.get(key) is not None for key in ('n2_executed_prefix_audit',
        'n3_executed_feedback_audit','n18_lift_quality_audit','n22_hold_lift_quality_audit',
        'n23_actuator_clipped_quality_audit')),'N7 omitted mode cannot admit a different quality intervention')
    for decision in gate['decisions']:
        raw=decision.get('terminal_raw_provider_quality',{});cost=decision.get('terminal_native_costs',{})
        w.require(raw.get('shape')==cost.get('shape')==[16]
            and raw.get('dtype')==cost.get('dtype') and raw.get('dtype') in {'torch.float32','torch.bfloat16'}
            and isinstance(raw.get('sha256'),str) and len(raw['sha256'])==64
            and isinstance(cost.get('sha256'),str) and len(cost['sha256'])==64
            and len(raw.get('values',[]))==len(cost.get('values',[]))==16,
            'N7 omitted mode native raw record malformed')
        w.require(all(type(q) in (int,float) and type(v) in (int,float) and math.isfinite(q)
            and math.isfinite(v) and v==-q for q,v in zip(raw['values'],cost['values'])),
            'N7 omitted mode native quality is not original raw provider')
        index=decision.get('selected_index')
        w.require(type(index) is int and 0<=index<16
            and decision.get('selected_raw_reward')==raw['values'][index]
            and decision.get('selected_cost')==cost['values'][index],
            'N7 omitted mode selected raw/cost binding differs')


def native_counts(final,row,report,*,plan,manifest,root,r,w,original):
    if row['profile']!='N7':
        # In particular, a missing N23 quality mode remains an original failure.
        return original.native_counts(final,row,report)
    verify_provider_profile(plan,manifest,root,w)
    metrics=r['read_events'](Path(final['output_dir'])/'eds_eval/eds_metrics.jsonl')
    n=len(metrics)
    w.require(final.get('guided_chunks')==n,'N7 native/compute guided count differs')
    if n==0:return original.native_counts(final,row,report)
    raw_provider_evidence(report,n,w)
    w.require(all(m.get('qd_archive_active_for_chunk') is True
        and ('qd_quality_mode' not in m or m['qd_quality_mode']=='provider')
        and m.get('score_call_count')==11 and m.get('search_evaluation_count')==176
        and all(m.get(k)==10 for k in ('resample_count','renoise_count','rollout_count')) for m in metrics),
        'N7 legacy provider-mode/fixed QD/ED metrics differ')
    return {'guided_decisions':n,'parent_rounds_verified':10*n},{k:0 for k in original.AUX_FIELDS}

