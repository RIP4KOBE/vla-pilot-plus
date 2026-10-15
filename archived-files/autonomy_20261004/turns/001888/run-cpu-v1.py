import subprocess,pathlib,json,datetime
p=pathlib.Path(__file__).resolve().parent
r=subprocess.run(["/home/hynx/miniconda3/envs/vla-pilot/bin/python","-B","-X","pycache_prefix=/dev/null",str(p/"review-readiness-v1.py")])
(p/"cpu-exit-v1.json").write_text(json.dumps(dict(returncode=r.returncode,at=datetime.datetime.now(datetime.timezone.utc).isoformat())))
