"""Read-only NumPy audit of already saved diagnostic frames; no simulator imports."""
import hashlib
import json
from pathlib import Path
import numpy as np

A = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
FOLDER = A / 'runtime/gpu3-native-render-lifetime-diagnostic'


def sha(data): return hashlib.sha256(data).hexdigest()


def analyze():
    contract_path = FOLDER / 'frozen-contract.json'
    contract = json.loads(contract_path.read_text())
    output = Path(contract['output_dir'])
    assert output.parent == FOLDER
    events_path = output / 'native_render_lifetime_events.jsonl'
    events = [json.loads(line) for line in events_path.read_text().splitlines() if line.strip()]
    rows = []
    for frame in events:
        if frame.get('event') != 'raw_frame_artifact': continue
        for kind in ('rgb', 'depth'):
            item = frame[kind]
            if item is None: continue
            path = Path(item['path'])
            assert path.is_relative_to(output / 'frames')
            assert sha(path.read_bytes()) == item['npy_sha256']
            array = np.load(path, allow_pickle=False)
            assert sha(array.tobytes()) == item['array_sha256']
            assert str(array.dtype) == item['dtype'] and list(array.shape) == item['shape']
            row = {'path': str(path), 'kind': kind, 'camera_key': frame['camera_key'],
                'array_sha256': item['array_sha256'], 'npy_sha256': item['npy_sha256'],
                'shape': list(array.shape), 'dtype': str(array.dtype),
                'finite': bool(np.isfinite(array).all()), 'minimum': float(array.min()),
                'maximum': float(array.max()), 'mean': float(array.mean()), 'std': float(array.std())}
            if kind == 'rgb':
                row['canonical_rgb_sha256'] = frame['canonical_rgb_sha256']
                row['canonical_rgb_matches'] = item['array_sha256'] == frame['canonical_rgb_sha256']
                row['canonical_pixel_difference'] = None
                row['reason'] = 'canonical raw pixel array was not saved; hash mismatch gives no magnitude'
            else:
                row['canonical_depth_equal'] = None
                row['reason'] = 'canonical depth raw array and depth hash were not recorded'
            rows.append(row)
    assert len(rows) == 4 and all(row['finite'] for row in rows)
    return {'mode': 'CPU saved-array analysis, no rendering', 'source_contract_sha256': sha(contract_path.read_bytes()),
        'source_events_sha256': sha(events_path.read_bytes()), 'historical_resource_id': contract['resource_id'],
        'analysis_boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'arrays': rows, 'old_failure_reclassified': False}


if __name__ == '__main__':
    print(json.dumps(analyze(), indent=2, sort_keys=True, allow_nan=False))
