import ctypes, os, sys, json
from pathlib import Path
out=Path(__file__).resolve().parent
libc=ctypes.CDLL(None,use_errno=True)
def checked(result):
    if result < 0: raise OSError(ctypes.get_errno(),os.strerror(ctypes.get_errno()))
    return result
abi=checked(libc.syscall(444,0,0,1))
assert abi>=3, ('Landlock ABI too old',abi)
mask=(1<<1)|sum(1<<i for i in range(4,15))
class Rules(ctypes.Structure): _fields_=[('handled_access_fs',ctypes.c_uint64)]
class Beneath(ctypes.Structure):
    _pack_=1
    _fields_=[('allowed_access',ctypes.c_uint64),('parent_fd',ctypes.c_int32)]
attr=Rules(mask)
fd=checked(libc.syscall(444,ctypes.byref(attr),ctypes.sizeof(attr),0))
parent=os.open(out,os.O_PATH|os.O_DIRECTORY)
rule=Beneath(mask,parent)
checked(libc.syscall(445,fd,1,ctypes.byref(rule),0))
checked(libc.prctl(38,1,0,0,0))
checked(libc.syscall(446,fd,0))
os.close(fd);os.close(parent)
def audit(event,args):
    if event in ('os.chmod','os.chown','os.utime','os.truncate') and not isinstance(args[0],int):
        if not Path(args[0]).resolve().is_relative_to(out):
            raise PermissionError('metadata outside repair output: '+str(args[0]))
sys.addaudithook(audit)
print(json.dumps({'landlock_abi':abi,'write_root':str(out),'inherited_by_subprocesses':True}),flush=True)
sys.path.insert(0,str(Path.cwd()))
import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
