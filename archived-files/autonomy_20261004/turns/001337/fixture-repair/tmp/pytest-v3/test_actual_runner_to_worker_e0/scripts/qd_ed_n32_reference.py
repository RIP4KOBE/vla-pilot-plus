"""Independent N32 all-cell reference; never imports production selector/helper.

Frozen N31 binary64 geometry is reused as an independent mathematical reference.
"""
from scripts.qd_ed_n31_reference import (require, same, shape, native_id, fingerprint, reconstruct)


def enumerate_parents(archive, entries, iteration, mask, target, packet):
    require(0 < len(archive) <= 16 and len(entries) == 16 * (iteration + 1), 'N32 archive/cache coverage')
    candidates, parents = [], []
    for cell, entry in sorted(archive.items()):
        require(type(cell) is int and 0 <= cell < 16 and -1 <= entry['source_iter'] < iteration, 'N32 cell/source')
        plan = shape(entry['plan'], (64, 128), True)
        require(same(plan * mask[0], plan) and fingerprint(plan) == entry['fingerprint'], 'N32 parent mask/fingerprint')
        matches = [e for e in entries if e['iteration'] == entry['source_iter']
                   and e['fingerprint'] == entry['fingerprint'] and same(e['plan'], plan)]
        require(bool(matches), 'N32 missing canonical association')
        first = matches[0]
        for row in matches:
            require(row['projection_status'] == 'original_canonical', 'N32 missing original projection')
            shape(row['projection'], (8, 3), True)
            require(row['projection'].dtype == plan.dtype, 'N32 projection dtype')
            for key in ('quality', 'cost', 'projection', 'source_origin', 'cast_origin'):
                require(same(row[key], first[key]), 'N32 contradictory duplicate ' + key)
            require(same(row['source_origin'].to(plan.dtype), row['cast_origin'])
                    and same(row['cost'], -row['quality'])
                    and float(row['quality']) == entry['reward'] and float(row['cost']) == entry['cost'],
                    'N32 native quality/cost/origin')
        candidate, arrival, reason = reconstruct(plan, first['projection'], target,
            packet['hand_quaternion_xyzw'], packet['gripper_qpos'])
        association = 'unique_occurrence' if len(matches) == 1 else 'identical_content_multiple_occurrences'
        parents.append({'cell_id': cell, 'source_iter': entry['source_iter'], 'fingerprint': entry['fingerprint'],
            'matching_occurrences': [r['occurrence'] for r in matches], 'association': association,
            'reason': reason, 'arrival_index': arrival, 'eligible': candidate is not None,
            'archive': {'cell': cell, 'source_iter': entry['source_iter'], 'insert_sequence': entry['insert_sequence'],
                        'fingerprint': entry['fingerprint'], 'native_identity': native_id(plan)}, 'source': first})
        if candidate is not None:
            require(same(candidate * mask[0], candidate), 'N32 candidate mask')
            candidates.append(((-entry['reward'], entry['fingerprint'], cell), candidate, arrival, reason))
    if not candidates:
        return parents, None, None, None, 'no_eligible_parent'
    rank, candidate, arrival, reason = sorted(candidates, key=lambda item: item[0])[0]
    return parents, rank[2], candidate, arrival, reason
