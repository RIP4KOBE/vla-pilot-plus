import pathlib,json,subprocess,datetime
p=pathlib.Path(__file__).parent
s=json.loads((p/'launch-spec-v1.json').read_text())
def identity(pid):
 b=pathlib.Path(f"/proc/{pid}/stat").read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(b[19]))
with (p/'prompt.txt').open() as inp,(p/'events.jsonl').open('w') as out,(p/'stderr.log').open('w') as err:
 c=subprocess.Popen(s['argv'],cwd=s['cwd'],stdin=inp,stdout=out,stderr=err)
 (p/'process-v1.json').write_text(json.dumps(identity(c.pid),indent=2))
 rc=c.wait()
 (p/'exit-v1.json').write_text(json.dumps(dict(exit=rc,at=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2))
