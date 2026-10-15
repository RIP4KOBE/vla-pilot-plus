import ctypes,json,os,signal,subprocess,time
from pathlib import Path
PID=1502190
EXPECTED_START="363452636"
EXPECTED_UUID="GPU-a5d6a5f8-b6df-7f3a-c3dc-19734c41ec0e"
result={"physical_gpu":2,"pid":PID,"expected_start_ticks":EXPECTED_START,"signals":[],"time_unix":time.time()}
def identity():
    try:
        fields=Path(f"/proc/{PID}/stat").read_text().rsplit(")",1)[1].split()
        return fields[19],fields[0]
    except FileNotFoundError:return None,None
start,state=identity()
if start is None or state in {"Z","X"}:
    result["status"]="already_stopped";print(json.dumps(result));raise SystemExit(0)
assert start==EXPECTED_START,"PID identity changed; refusing signal"
apps=subprocess.run(["nvidia-smi","--query-compute-apps=gpu_uuid,pid","--format=csv,noheader,nounits"],check=True,capture_output=True,text=True,timeout=15)
bindings={line.split(",")[0].strip() for line in apps.stdout.splitlines() if line.split(",")[-1].strip()==str(PID)}
assert bindings=={EXPECTED_UUID},"Process GPU ownership differs from authorized GPU2"
libc=ctypes.CDLL(None,use_errno=True)
fd=libc.pidfd_open(PID,0)
if fd<0:raise OSError(ctypes.get_errno(),"pidfd_open")
try:
    assert identity()[0]==EXPECTED_START,"PID reused before signal"
    for sig,grace in ((signal.SIGTERM,15),(signal.SIGKILL,10)):
        if identity()[0] is None or identity()[1] in {"Z","X"}:break
        rc=libc.pidfd_send_signal(fd,int(sig),None,0)
        if rc<0:raise OSError(ctypes.get_errno(),"pidfd_send_signal")
        result["signals"].append(sig.name)
        deadline=time.monotonic()+grace
        while time.monotonic()<deadline:
            if identity()[0] is None or identity()[1] in {"Z","X"}:break
            time.sleep(0.25)
    remaining=identity()
    result["status"]="stopped" if remaining[0] is None or remaining[1] in {"Z","X"} else "still_running"
finally:os.close(fd)
print(json.dumps(result))
raise SystemExit(0 if result["status"]=="stopped" else 1)
