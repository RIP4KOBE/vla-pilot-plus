import subprocess,pathlib,json,datetime
p=pathlib.Path(__file__).resolve().parent
with (p/"cpu.stdout.log").open("ab") as out,(p/"cpu.stderr.log").open("ab") as err:
 r=subprocess.run(["/home/hynx/miniconda3/envs/vla-pilot/bin/python","-B",str(p/"review-readiness-v1.py")],stdout=out,stderr=err)
(p/"cpu-exit-v1.json").write_text(json.dumps(dict(returncode=r.returncode,at=datetime.datetime.now(datetime.timezone.utc).isoformat()))+"\n")
