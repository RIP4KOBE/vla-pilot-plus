"""Read-only request accounting from complete audited three-mode reports."""
import argparse, collections, hashlib, json, math
from pathlib import Path

def summarize(path):
    report=json.loads(path.read_text())
    if not report['all_cohorts_valid']:raise ValueError('Full valid cohorts required')
    result={'report_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'commit':report['common_commit'],'modes':{}}
    for mode,run in report['runs'].items():
        if not run['accepted']:raise ValueError('Unaccepted cohort')
        records=[];recovery=[];counts=collections.Counter();signals=collections.Counter()
        for p in sorted((Path(run['run_dir'])/'output').rglob('response.json')):
            r=json.loads(p.read_text());t=r['transport'];attempts=t['physical_call_attempts']
            assert r['ok'] and attempts==len(t['failed_transport_attempts'])+1
            counts[attempts]+=1;records.append(r)
            if attempts>1:
                failed=t['failed_transport_attempts'];ss=set()
                for f in failed:
                    ss.update(f.get('stderr_diagnostic',{}).get('signals',[]))
                    for d in f.get('error_diagnostics',[]):ss.update(d.get('signals',[]))
                signals.update(ss)
                recovery.append({'path':str(p),'physical_attempts':attempts,'signals':sorted(ss)})
        assert records
        latency=sorted(r['counters']['call_latency_s'] for r in records)
        counters={}
        for key in ('logical_call_attempts','completed_turns','failed_calls','input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens','call_latency_s'):
            vals=[r['counters'][key] for r in records]
            counters[key]={'total':sum(vals) if all(v is not None for v in vals) else None,'known_records':sum(v is not None for v in vals),'total_records':len(vals)}
        physical=sum(k*v for k,v in counts.items());assert counters['logical_call_attempts']['total']==physical
        result['modes'][mode]={'captured_logical_requests':len(records),'physical_cli_attempts':physical,'recovered_requests':len(recovery),'physical_attempt_histogram':dict(counts),'recovery_signals_by_request':dict(signals),'latency_seconds':{'total':sum(latency),'mean':sum(latency)/len(latency),'median':(latency[(len(latency)-1)//2]+latency[len(latency)//2])/2,'p95_nearest_rank':latency[math.ceil(.95*len(latency))-1],'maximum':max(latency)},'capture_counters':counters,'recovery_receipts':recovery,'limits':['Latency includes transport recovery/backoff and server wait.','Legacy logical_call_attempts counter counts physical CLI attempts; captured_logical_requests counts full captured request records.','Local metadata is not independent attestation of server model identity.']}
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise FileExistsError('Preserve existing report')
    result=summarize(a.report);a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print({m:{k:v[k] for k in ('captured_logical_requests','physical_cli_attempts','recovered_requests','latency_seconds')} for m,v in result['modes'].items()})
