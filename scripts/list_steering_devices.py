"""Identify the EGL device for one NVIDIA GPU without loading models or rendering.

Run in a separate process before configuring a local steering environment.
The subsequent GPU preflight still needs to verify actual CUDA and rendering.
"""
from __future__ import annotations

import argparse
import ctypes as C
import json
import os
import subprocess


def unique_egl_index(devices):
    matches = [d['egl_index'] for d in devices if d['visible_cuda_ordinal'] == 0]
    if len(matches) != 1:
        raise RuntimeError(f'Expected one EGL device for visible CUDA device 0; found {matches}')
    return matches[0]


def extension(library, name, restype, *arguments):
    library.eglGetProcAddress.argtypes = [C.c_char_p]
    library.eglGetProcAddress.restype = C.c_void_p
    address = library.eglGetProcAddress(name.encode())
    if not address:
        raise RuntimeError(f'EGL extension unavailable: {name}')
    return C.CFUNCTYPE(restype, *arguments)(address)


def device_mapping(gpu):
    if gpu < 0:
        raise ValueError('GPU index must be nonnegative')
    metadata = subprocess.check_output([
        'nvidia-smi', '-i', str(gpu), '--query-gpu=uuid,pci.bus_id,name',
        '--format=csv,noheader,nounits'], text=True, timeout=30).strip().split(', ', 2)
    if len(metadata) != 3:
        raise RuntimeError('Unexpected nvidia-smi device metadata')
    os.environ['CUDA_VISIBLE_DEVICES'] = str(gpu)
    os.environ['CUDA_DEVICE_ORDER'] = 'PCI_BUS_ID'
    cuda = C.CDLL('libcuda.so.1')
    if cuda.cuInit(0) != 0:
        raise RuntimeError('CUDA driver initialization failed')
    count, device = C.c_int(), C.c_int()
    if cuda.cuDeviceGetCount(C.byref(count)) != 0 or count.value != 1:
        raise RuntimeError('Expected exactly one visible CUDA device')
    if cuda.cuDeviceGet(C.byref(device), 0) != 0:
        raise RuntimeError('Cannot inspect CUDA device 0')

    class UUID(C.Structure):
        _fields_ = [('data', C.c_ubyte * 16)]

    uid = UUID()
    if cuda.cuDeviceGetUuid_v2(C.byref(uid), device) != 0:
        raise RuntimeError('Cannot query CUDA device UUID')
    value = bytes(uid.data).hex()
    actual = 'GPU-' + '-'.join((value[:8], value[8:12], value[12:16], value[16:20], value[20:]))
    if actual != metadata[0]:
        raise RuntimeError('CUDA ordinal does not match the requested nvidia-smi GPU UUID')

    egl = C.CDLL('libEGL.so.1')
    query = extension(egl, 'eglQueryDevicesEXT', C.c_uint, C.c_int,
                      C.POINTER(C.c_void_p), C.POINTER(C.c_int))
    attribute = extension(egl, 'eglQueryDeviceAttribEXT', C.c_uint, C.c_void_p,
                          C.c_int, C.POINTER(C.c_ssize_t))
    total = C.c_int()
    if not query(0, None, C.byref(total)) or total.value <= 0:
        raise RuntimeError('Cannot enumerate EGL devices')
    handles = (C.c_void_p * total.value)()
    if not query(total.value, handles, C.byref(total)):
        raise RuntimeError('Cannot retrieve EGL devices')
    devices = []
    for index in range(total.value):
        ordinal = C.c_ssize_t(-1)
        ok = attribute(handles[index], 0x323A, C.byref(ordinal))  # EGL_CUDA_DEVICE_NV
        devices.append({'egl_index': index, 'handle': int(handles[index]),
                        'visible_cuda_ordinal': int(ordinal.value) if ok else None})
    return {'gpu': gpu, 'uuid': actual, 'pci_bus_id': metadata[1], 'name': metadata[2],
            'egl_device_id': unique_egl_index(devices), 'egl_devices': devices,
            'scope': 'driver identity and EGL enumeration only; no allocation/render/model/API test'}


def current_render_device_handle():
    """Inspect the current display while the caller's EGL environment is alive."""
    egl = C.CDLL('libEGL.so.1')
    egl.eglGetCurrentDisplay.restype = C.c_void_p
    display = egl.eglGetCurrentDisplay()
    query = extension(egl, 'eglQueryDisplayAttribEXT', C.c_uint, C.c_void_p,
                      C.c_int, C.POINTER(C.c_ssize_t))
    device = C.c_ssize_t()
    if not display or not query(display, 0x322C, C.byref(device)):  # EGL_DEVICE_EXT
        raise RuntimeError('Cannot identify the current rendering display device')
    return int(device.value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gpu', type=int, required=True, help='Assigned physical nvidia-smi index')
    args = parser.parse_args()
    print(json.dumps(device_mapping(args.gpu), indent=2))


if __name__ == '__main__':
    main()
