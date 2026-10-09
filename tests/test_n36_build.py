"""Synthetic files/maps only; never load a library or probe CUDA."""
import json
from pathlib import Path
import pytest
import torch
from scripts import qd_ed_n36_build as build, qd_ed_n23_worker as w


def synthetic_build(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    libraries=[]
    for name in (*build.REQUIRED,'libcuda.so.1'):
        file=root/name;file.write_text('synthetic fixture, not an executable library\n')
        libraries.append({'path':str(file.resolve()),'sha256':w.sha(file)})
    value={'schema':'n36-native-build-v1','torch_version':str(torch.__version__),'cuda_version':torch.version.cuda,
        'torch_build':torch.__config__.show(),'libraries':sorted(libraries,key=lambda r:r['path'])}
    file=root/'build.json';file.write_text(json.dumps(value))
    return {'path':str(file.resolve()),'sha256':w.sha(file)}


def test_actual_maps_are_externally_bound_and_missing_or_changed_reject(tmp_path,monkeypatch):
    reference=synthetic_build(tmp_path);expected=w.read_ref(reference)
    maps='\n'.join('0000-1000 r-xp 0 00:00 1 '+r['path'] for r in expected['libraries'])
    original=Path.read_text
    monkeypatch.setattr(Path,'read_text',lambda path,*a,**kw:maps if str(path)=='/proc/self/maps' else original(path,*a,**kw))
    receipt=build.attest(reference,after=True)
    assert build.verify_receipt(reference,receipt,after=True)==receipt
    maps+='\n0000-1000 r-xp 0 00:00 2 '+str(tmp_path/'libtorch_unbound.so')
    with pytest.raises(ValueError,match='unbound'):build.attest(reference,after=True)
    missing={**receipt,'libraries':receipt['libraries'][:-1]}
    with pytest.raises(ValueError):build.verify_receipt(reference,missing,after=True)
    Path(expected['libraries'][0]['path']).write_text('changed binary')
    with pytest.raises(ValueError,match='binary bytes'):build.attest(reference,after=True)
    assert not torch.cuda.is_initialized()


def test_deleted_library_and_unanchored_pass_flag_reject(tmp_path):
    with pytest.raises(ValueError,match='deleted'):
        build.mapped_libraries('0000-1000 r-xp 0 00:00 1 /tmp/libtorch_cuda.so (deleted)')
    reference=synthetic_build(tmp_path);receipt={'schema':'n36-loaded-native-build-v1','manifest':reference,'libraries':[],'PASS':True}
    with pytest.raises(ValueError):build.verify_receipt(reference,receipt,after=True)
