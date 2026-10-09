"""Bind actual mapped Torch/CUDA libraries to a prospective external inventory.

No library is loaded or probed by this module. Reading maps/hashing is passive.
The coordinator supplies the inventory before release; observed files never
become their own trust anchor.
"""
from pathlib import Path
import torch
from scripts import qd_ed_n23_worker as w

PREFIXES=('libtorch','libc10','libcuda','libcublas','libcudnn','libcufft','libcurand',
          'libcusparse','libcusolver','libnvrtc','libnvJitLink','libnccl')
REQUIRED=('libtorch_cpu.so','libtorch_cuda.so','libtorch_python.so','libc10.so','libc10_cuda.so')


def manifest(reference):
    value=w.read_ref(reference)
    w.require(set(value)=={'schema','torch_version','cuda_version','torch_build','libraries'}
        and value['schema']=='n36-native-build-v1','native build schema')
    rows=value['libraries']
    w.require(isinstance(rows,list) and rows and len({r['path'] for r in rows})==len(rows),'native library inventory')
    for row in rows:
        path=Path(row['path'])
        w.require(set(row)=={'path','sha256'} and path.is_absolute() and str(path.resolve())==str(path)
            and path.is_file() and not path.is_symlink() and w.sha(path)==row['sha256'],'native binary bytes/path')
    names={Path(r['path']).name for r in rows}
    w.require(set(REQUIRED)<=names and any(x.startswith('libcuda.so') for x in names),'native CUDA build incomplete')
    return value


def mapped_libraries(text):
    files=set()
    for line in text.splitlines():
        columns=line.split(maxsplit=5)
        if len(columns)!=6 or not columns[5].startswith('/'):continue
        raw=columns[5];name=Path(raw).name
        if name.startswith(PREFIXES) or ('/torch/' in raw and '.so' in name):
            w.require(not raw.endswith(' (deleted)'),'deleted mapped native binary')
            files.add(str(Path(raw).resolve()))
    return sorted(files)


def attest(reference, *, after=False):
    expected=manifest(reference)
    w.require(expected['torch_version']==str(torch.__version__) and expected['cuda_version']==torch.version.cuda
        and expected['torch_build']==torch.__config__.show(),'actual native build metadata')
    paths=mapped_libraries(Path('/proc/self/maps').read_text())
    index={r['path']:r['sha256'] for r in expected['libraries']}
    rows=[]
    for path in paths:
        w.require(path in index and w.sha(path)==index[path],'unbound actual loaded Torch/CUDA library')
        rows.append({'path':path,'sha256':index[path]})
    receipt={'schema':'n36-loaded-native-build-v1','manifest':reference,'libraries':rows}
    verify_receipt(reference,receipt,after=after)
    return receipt


def verify_receipt(reference, receipt, *, after=False):
    expected=manifest(reference)
    w.require(set(receipt)=={'schema','manifest','libraries'} and receipt['schema']=='n36-loaded-native-build-v1'
        and receipt['manifest']==reference,'native build receipt binding')
    rows=receipt['libraries'];index={r['path']:r['sha256'] for r in expected['libraries']}
    w.require(rows and rows==sorted(rows,key=lambda r:r['path']) and len({r['path'] for r in rows})==len(rows)
        and all(set(r)=={'path','sha256'} and index.get(r['path'])==r['sha256'] for r in rows),'mapped binary inventory receipt')
    if after:
        names={Path(r['path']).name for r in rows}
        w.require(set(REQUIRED)<=names and any(n.startswith('libcuda.so') for n in names),'actual CUDA kernels/driver not mapped')
    return receipt
