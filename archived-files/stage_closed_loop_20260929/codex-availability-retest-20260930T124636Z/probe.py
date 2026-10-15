from pathlib import Path
import base64,datetime,json,sys,time
root=Path(sys.argv[1]);dest=Path(sys.argv[2]);source=Path(sys.argv[3]);sys.path.insert(0,str(root))
from core.codex_vision import CodexVisionTransport
from core.stage_evidence import parse_observation
config=dict(backend='codex_cli',model='gpt-6-astra',reasoning_effort='low',event_policy='completed_transport_cycles_v6',timeout_seconds=180,transport_retry_count=0,capture_dir=str(dest/'requests'))
parts=json.loads((source/'parts.json').read_text())
content=[dict(type='text',text=p['text']) if p['type']=='text' else dict(type='image_url',image_url=dict(url='data:image/png;base64,'+base64.b64encode((source/p['file']).read_bytes()).decode())) for p in parts]
transport=CodexVisionTransport(config);start=time.perf_counter();report=dict(start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_capture=str(source),model=config['model'],reasoning_effort=config['reasoning_effort'],scope='independent diagnostic, not a rollout')
try:
 reply=transport._request_stage_response(content)
 observation=parse_observation(reply)
 report.update(status='PASS',schema_valid=True,observation=observation)
except Exception as exc:
 report.update(status='FAIL',error_type=type(exc).__name__)
finally:
 report.update(end_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),seconds=time.perf_counter()-start,counter=transport.api_request_counter.snapshot())
 (dest/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(report,ensure_ascii=False),flush=True)
