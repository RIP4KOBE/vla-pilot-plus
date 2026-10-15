#!/usr/bin/env python3
"""Authorized small CUDA/EGL/LIBERO reset-render probe; no actions/models/API."""
import argparse
import ctypes as C
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def run(*argv):
    return subprocess.check_output(argv, text=True, timeout=30).strip()


def egl_function(lib, name, restype, *args):
    lib.eglGetProcAddress.restype = C.c_void_p
    lib.eglGetProcAddress.argtypes = [C.c_char_p]
    address = lib.eglGetProcAddress(name.encode())
    if not address:
        raise RuntimeError('Missing EGL extension: ' + name)
    return C.CFUNCTYPE(restype, *args)(address)


def inspect_egl():
    lib = C.CDLL('libEGL.so.1')
    query = egl_function(lib, 'eglQueryDevicesEXT', C.c_uint, C.c_int, C.POINTER(C.c_void_p), C.POINTER(C.c_int))
    attribute = egl_function(lib, 'eglQueryDeviceAttribEXT', C.c_uint, C.c_void_p, C.c_int, C.POINTER(C.c_ssize_t))
    string = egl_function(lib, 'eglQueryDeviceStringEXT', C.c_char_p, C.c_void_p, C.c_int)
    count = C.c_int()
    devices = (C.c_void_p * 64)()
    assert query(64, devices, C.byref(count))
    records = []
    for index in range(count.value):
        ordinal = C.c_ssize_t(-999)
        ok = bool(attribute(devices[index], 0x323A, C.byref(ordinal))) # EGL_CUDA_DEVICE_NV
        drm = string(devices[index], 0x3233) # EGL_DRM_DEVICE_FILE_EXT
        record = {'egl_index':index, 'handle':int(devices[index]), 'cuda_attribute_ok':ok,
                  'visible_cuda_ordinal':int(ordinal.value) if ok else None,
                  'drm_device_file':drm.decode() if drm else None}
        if drm:
            node = Path('/sys/class/drm') / Path(drm.decode()).name / 'device'
            if node.exists(): record['sysfs_pci_bus_id'] = node.resolve().name
        records.append(record)
    return lib, records


def gpu_processes(gpu):
    raw = run('nvidia-smi','-i',str(gpu),'-q','-x')
    tree = ET.fromstring(raw)
    rows=[]
    for process in tree.findall('.//process_info'):
        rows.append({child.tag:child.text for child in process})
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo-root',type=Path,required=True);p.add_argument('--local-config',type=Path,required=True)
    p.add_argument('--gpu',type=int,choices=[0,1,4],required=True);p.add_argument('--expected-uuid',required=True)
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();a.repo_root=a.repo_root.resolve();a.report=a.report.resolve()
    a.report.parent.mkdir(parents=True,exist_ok=True)
    with a.report.open('x') as f: f.write('{}\n')
    report={'schema':'steering_gpu_render_mapping_v1','scope':'CUDA allocation and LIBERO reset/render only; no actions, model weights, API, or task outcome',
            'pid':os.getpid(),'physical_gpu':a.gpu,'expected_uuid':a.expected_uuid,
            'started_unix':time.time(),'allocator_limit_bytes':2*1024**3,'status':'running',
            'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'limitations':['2 GiB is the PyTorch allocator cap; CUDA/EGL context and library memory are outside this cap.']}
    lock=None;environment=None;torch=None
    try:
        if os.environ.get('CUDA_VISIBLE_DEVICES')!=str(a.gpu) or os.environ.get('CUDA_DEVICE_ORDER')!='PCI_BUS_ID':
            raise RuntimeError('Require explicit authorized CUDA mask and PCI_BUS_ID order')
        lock_path=a.repo_root/f'.worktrees/exp/steering-integration/gpu-{a.gpu}.lock'
        lock_path.parent.mkdir(parents=True,exist_ok=True);lock=lock_path.open('a+')
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        metadata=run('nvidia-smi','-i',str(a.gpu),'--query-gpu=index,uuid,pci.bus_id,name,memory.used','--format=csv,noheader,nounits').split(', ')
        if metadata[1]!=a.expected_uuid or int(metadata[-1])>64 or gpu_processes(a.gpu):
            raise RuntimeError('GPU identity differs or GPU is not idle')
        report['nvidia_before']=dict(zip(('index','uuid','pci_bus_id','name','memory_used_mib'),metadata))
        report['boot_id']=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        cuda=C.CDLL('libcuda.so.1');assert cuda.cuInit(0)==0
        count=C.c_int();assert cuda.cuDeviceGetCount(C.byref(count))==0 and count.value==1
        dev=C.c_int();assert cuda.cuDeviceGet(C.byref(dev),0)==0
        class UUID(C.Structure): _fields_=[('data',C.c_ubyte*16)]
        uid=UUID();assert cuda.cuDeviceGetUuid_v2(C.byref(uid),dev)==0
        hx=bytes(uid.data).hex();uuid='GPU-'+hx[:8]+'-'+hx[8:12]+'-'+hx[12:16]+'-'+hx[16:20]+'-'+hx[20:]
        pci=C.create_string_buffer(64);assert cuda.cuDeviceGetPCIBusId(pci,64,dev)==0
        assert uuid==a.expected_uuid
        report['cuda_driver_metadata']={'uuid':uuid,'pci_bus_id':pci.value.decode(),'context_created':False}
        egl, devices=inspect_egl();report['egl_devices']=devices
        matches=[d for d in devices if d['cuda_attribute_ok'] and d['visible_cuda_ordinal']==0]
        if len(matches)!=1:raise RuntimeError('No unique EGL device maps to visible CUDA device0')
        selected=matches[0];report['verified_egl_index']=selected['egl_index']
        sys.path.insert(0,str(a.repo_root))
        from scripts.steering_runtime import load_local,runtime_environment
        local=load_local(a.local_config);local.update(gpu=a.gpu,egl_device_id=selected['egl_index'],allocator_limit_gib=2)
        env=runtime_environment(local);env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1')
        os.environ.clear();os.environ.update(env)
        for path in reversed(env['PYTHONPATH'].split(os.pathsep)):
            if path not in sys.path:sys.path.insert(0,path)
        import torch as torch_module
        torch=torch_module
        prop=torch.cuda.get_device_properties(0)
        torch.cuda.set_per_process_memory_fraction((2*1024**3)/prop.total_memory,0)
        value=torch.ones(32,device='cuda:0').square().sum().item();torch.cuda.synchronize()
        report['cuda_probe']={'sum':value,'torch':torch.__version__,'torch_cuda':torch.version.cuda,'property_uuid':str(getattr(prop,'uuid',None))}
        own_pid=str(os.getpid())
        compute=run('nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_gpu_memory','--format=csv,noheader,nounits')
        own=[row.strip().split(', ') for row in compute.splitlines() if row.strip().split(', ')[0]==own_pid]
        if not own or {row[1] for row in own}!={a.expected_uuid}:raise RuntimeError('Allocated own PID has wrong GPU identity')
        report['own_compute_processes']=own
        import libero
        from libero.libero.benchmark import get_benchmark_dict
        from libero.libero.envs import OffScreenRenderEnv
        from libero.libero import get_libero_path
        task=get_benchmark_dict()['libero_object_swap']().get_task(0)
        task_path=Path(get_libero_path('bddl_files'))/task.problem_folder/task.bddl_file
        environment=OffScreenRenderEnv(bddl_file_name=str(task_path),camera_heights=128,camera_widths=128)
        observation=environment.reset()
        frame=environment.sim.render(camera_name='agentview',height=128,width=128)
        assert list(observation['agentview_image'].shape)==[128,128,3] and list(frame.shape)==[128,128,3]
        report['render']={'task_name':task.name,'reset_image_shape':list(observation['agentview_image'].shape),'explicit_render_shape':list(frame.shape),
                          'image_sha256':hashlib.sha256(frame.tobytes()).hexdigest(),'libero_module':libero.__file__,'environment_steps':0}
        egl.eglGetCurrentDisplay.restype=C.c_void_p
        display=egl.eglGetCurrentDisplay()
        query_display=egl_function(egl,'eglQueryDisplayAttribEXT',C.c_uint,C.c_void_p,C.c_int,C.POINTER(C.c_ssize_t))
        display_device=C.c_ssize_t()
        if not display or not query_display(display,0x322C,C.byref(display_device)) or display_device.value!=selected['handle']:
            raise RuntimeError('Actual current rendering display is not the verified EGL device')
        report['actual_render_display']={'handle':int(display),'device_handle':display_device.value,'matches_verified_device':True}
        rows=gpu_processes(a.gpu);report['nvidia_processes_after_render']=rows
        own_graphics=[r for r in rows if r.get('pid')==own_pid and 'G' in r.get('type','')]
        if not own_graphics:raise RuntimeError('Own PID graphics-process evidence not available')
        report['own_graphics_pid_verified']=True
        report['peak_allocated_bytes']=torch.cuda.max_memory_allocated(0)
        report['peak_reserved_bytes']=torch.cuda.max_memory_reserved(0)
        assert report['peak_reserved_bytes']<=2*1024**3
        report['status']='pass'
    except Exception as e:
        report['status']='fail';report['error']={'type':type(e).__name__,'message':str(e)}
    finally:
        if environment is not None:environment.close()
        report['cuda_initialized']=bool(torch is not None and torch.cuda.is_initialized())
        report['completed_unix']=time.time()
        a.report.write_text(json.dumps(report,indent=2)+'\n')
        if lock is not None:lock.close()
    print(json.dumps({'report':str(a.report),'status':report['status'],'gpu':a.gpu,'egl':report.get('verified_egl_index'),'error':report.get('error')}),flush=True)
    return 0 if report['status']=='pass' else 2

if __name__=='__main__':raise SystemExit(main())
