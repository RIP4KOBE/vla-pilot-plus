"""Read completed demonstrations from the user-authorized ticket collection.

This module does not curate demonstrations, repair datasets, start collectors,
or modify tickets. A completed curation artifact is the only readiness signal.
"""
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from .io import read_json, write_json, digest
from .protocol import TRAIN_SPLIT


def snapshot_curated_source(task_key, protocol, ticket_root, snapshot_root):
    snapshot_root = Path(snapshot_root)
    for path in sorted(Path(ticket_root).glob('*/curation.json')):
        value = read_json(path)
        if value.get('needs_more_demos') is not False or not value.get('export_root'):
            continue
        ticket_path = path.parent/'ticket.json'
        ticket = read_json(ticket_path)
        key = f"{ticket['suite']}::{ticket['task_id']}::{ticket['perturbation_variant']}"
        if key != task_key:
            continue
        unsigned = {k:v for k,v in value.items() if k!='curation_sha256'}
        check = hashlib.sha256(json.dumps(unsigned,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if check != value.get('curation_sha256') or digest(ticket_path) != value['ticket_sha256']:
            raise ValueError('curation/ticket provenance has changed')
        root = Path(value['export_root'])
        info = read_json(root/'meta/info.json')
        if int(info['total_episodes']) != len(value['accepted']):
            raise ValueError('curated demonstration count differs from the exported dataset')
        import h5py
        states = set()
        for file in value['accepted']:
            with h5py.File(file, 'r') as handle:
                state = handle.attrs['init_state_id']
                states.add(state.decode() if isinstance(state,bytes) else str(state))
                if str(handle.attrs['ticket_id']) != ticket['ticket_id']:
                    raise ValueError('demonstration belongs to another ticket')
        source = {'task_key':key, 'split':TRAIN_SPLIT,'init_state_ids':sorted(states),
                  'repo_id':value['repo_id'],'episodes':list(range(int(info['total_episodes']))),
                  'source_ticket_id':ticket['ticket_id'],'source_curation_sha256':check,
                  'acquisition_cost_source':'shared user-authorized ticket demonstrations; independent of main experiment progress'}
        protocol.validate_training_source(source)
        snapshot_root.mkdir(parents=True,exist_ok=True)
        destination = snapshot_root/(ticket['ticket_id']+'_'+check[:16])
        with (snapshot_root/'.copy.lock').open('a+') as lock:
            try:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                return None
            if not destination.exists():
                temporary = destination.with_name(destination.name+'.partial')
                temporary.mkdir(exist_ok=False)
                # Reflink where supported; idle I/O priority on hgpu1. Neither
                # command writes to the source tree.
                if sys.platform.startswith('linux') and shutil.which('ionice'):
                    subprocess.run(['ionice','-c','3','cp','-a','--reflink=auto',str(root),str(temporary/'lerobot')],check=True)
                else:
                    shutil.copytree(root,temporary/'lerobot')
                write_json(temporary/'curation.json',value)
                write_json(temporary/'ticket.json',ticket)
                temporary.rename(destination)
        source['root'] = str((destination/'lerobot').resolve())
        return source
    return None
