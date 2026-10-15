import subprocess,json,pathlib,datetime
out=pathlib.Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001455')
rec=json.loads((out/"health-operation-intent-v1.json").read_text())
with (out/"health-operation.log").open("w") as log:
 p=subprocess.Popen(rec["argv"],cwd=rec["cwd"],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 a=pathlib.Path(f"/proc/{p.pid}/stat").read_text().rsplit(")",1)[1].split()
 (out/"health-operation-process-v1.json").write_text(json.dumps({"pid":p.pid,"start_ticks":int(a[19]),"boot_id":pathlib.Path("/proc/sys/kernel/random/boot_id").read_text().strip()},indent=2)+"\n")
 code=p.wait()
(out/"health-operation-exit-v1.json").write_text(json.dumps({"exit":code,"at":datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+"\n")
