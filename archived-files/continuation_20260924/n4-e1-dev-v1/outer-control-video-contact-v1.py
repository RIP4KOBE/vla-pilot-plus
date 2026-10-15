#!/usr/bin/env python3
"""Sample existing matched control videos without changing study outcomes."""
import json
from pathlib import Path

import cv2
import numpy as np

root = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
manifest = json.loads((root / 'continuation_20260923/n4-e1-full12-report-v1/manifest.json').read_text())
out = root / 'continuation_20260924/n4-e1-dev-v1/outer-control-video-contact-v1'
out.mkdir(exist_ok=False)
rows = []
for spec in manifest['attempts']:
    terminal = json.loads(Path(spec['terminal']['path']).read_text())
    identity = terminal['identity']
    if identity['profile'] not in ('C0', 'Q0') or identity['task_id'] not in (0, 6, 9):
        continue
    videos = list(Path(spec['terminal']['path']).parent.glob('episode_1/*.mp4'))
    assert len(videos) == 1
    cap = cv2.VideoCapture(str(videos[0]))
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    assert count >= 5
    points = np.linspace(0, count - 1, 6, dtype=int)
    frames = []
    for index in points:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, frame = cap.read()
        assert ok
        frame = cv2.resize(frame, (320, 240))
        cv2.putText(frame, f't{identity["task_id"]:02d} {identity["profile"]} {index}/{count-1}',
                    (7, 22), cv2.FONT_HERSHEY_SIMPLEX, .6, (255, 255, 255), 2)
        frames.append(frame)
    cap.release()
    path = out / f't{identity["task_id"]:02d}-{identity["profile"].lower()}-contact.png'
    assert cv2.imwrite(str(path), np.concatenate(frames, axis=1))
    rows.append({'task_id': identity['task_id'], 'profile': identity['profile'],
                 'success': terminal['success'], 'frame_count': count,
                 'frame_indices': points.tolist(), 'source_video': str(videos[0]),
                 'contact_sheet': str(path)})
(out / 'sampling.json').write_text(json.dumps(rows, indent=2) + '\n')
print(json.dumps([{'task_id': row['task_id'], 'profile': row['profile'],
                   'success': row['success'], 'frame_count': row['frame_count']} for row in rows]))
