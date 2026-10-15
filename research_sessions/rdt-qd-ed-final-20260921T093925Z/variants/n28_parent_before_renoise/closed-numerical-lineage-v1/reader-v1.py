#!/usr/bin/env python3
"""Disabled until a separate hash-bound root release. No production imports."""
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import resource
import signal
import stat
import sys
import tempfile
import time
import zipfile

START = time.monotonic()
HERE = Path(__file__).resolve().parent
CAP = 64 * 1024 * 1024
PAYLOAD_TOTAL_CAP = 128 * 1024 * 1024
DECODED_TOTAL_CAP = 512 * 1024 * 1024
INDEX_KEYS = ('sequence', 'event', 'decision_id', 'global_step', 'reset_sequence')
TORCH = None


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def read_bound(path, cap, expected=None):
    p = Path(path)
    require(p.is_file() and p.stat().st_size <= cap, 'input size/type cap')
    with p.open('rb') as f:
        data = f.read(cap + 1)
    require(len(data) <= cap, 'input grew past cap')
    digest = hashlib.sha256(data).hexdigest()
    require(expected is None or digest == expected, 'input SHA mismatch')
    return data, digest


def write_new(path, data):
    with Path(path).open('x') as f:
        json.dump(data, f, indent=2, allow_nan=False)
        f.write('\n')


def install_guard(exact_reads, output):
    roots = tuple({Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve()})
    reads = {Path(p).resolve() for p in exact_reads}
    null_ok = stat.S_ISCHR(Path('/dev/null').stat().st_mode)
    denied = []
    def audit(event, args):
        if event.startswith(('socket.', 'subprocess.', 'os.system', 'os.exec', 'os.spawn')):
            denied.append(event)
            raise PermissionError('network/process forbidden')
        if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        p = Path(os.fsdecode(args[0]))
        if str(p) == '/proc/self/maps':
            mode, flags = args[1], args[2]
            if (isinstance(mode, str) and any(c in mode for c in 'wa+')) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
                raise PermissionError('maps readonly')
            return
        q = p.resolve()
        mode, flags = args[1], args[2]
        writing = ((isinstance(mode, str) and any(c in mode for c in 'wa+')) or
                   (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)))
        if q == Path('/dev/null') and null_ok:
            return
        if q.is_relative_to(output):
            return
        dependency = any(q.is_relative_to(root) for root in roots)
        if not writing and (q in reads or (dependency and q.suffix not in {'.pt', '.pth', '.bin', '.safetensors', '.npy', '.npz'})):
            return
        denied.append(str(q))
        raise PermissionError('read/write outside frozen inputs/dependencies/output')
    sys.addaudithook(audit)
    return denied


def finite_tensor(value, shape):
    t = TORCH
    require(t.is_tensor(value) and value.device.type == 'cpu' and tuple(value.shape) == tuple(shape), 'tensor shape/device')
    require(value.dtype in (t.bfloat16, t.float32) and bool(t.isfinite(value).all()), 'tensor dtype/nonfinite')
    return value


def distribution(values):
    t = TORCH
    x = values.detach().to(t.float64).reshape(-1)
    require(bool(t.isfinite(x).all()) and x.numel() > 0, 'summary finite/count')
    return {'n': x.numel(), 'min': x.min().item(), 'mean': x.mean().item(),
            'median': t.quantile(x, .5).item(), 'p90': t.quantile(x, .9).item(),
            'max': x.max().item(), 'zero_count': int((x == 0).sum())}


def support(value):
    # Comparisons occur in original native dtype. No epsilon bands.
    return {'components': value.numel(), 'minus_one': int((value == -1).sum()),
            'plus_one': int((value == 1).sum()), 'interior': int(((value > -1) & (value < 1)).sum()),
            'outside': int(((value < -1) | (value > 1)).sum())}


def describe(before, after, operand):
    t = TORCH
    before = finite_tensor(before, (16, 8, 3)); after = finite_tensor(after, (16, 8, 3))
    operand = finite_tensor(operand, (16, 8, 3))
    require(before.dtype == after.dtype == operand.dtype, 'native dtype disagreement')
    b, a, p = [x.detach().to(t.float64) for x in (before, after, operand)]
    d = a - b; B = b.reshape(16, 24); D = d.reshape(16, 24)
    centered = B - B.mean(0)
    _, singular, vh = t.linalg.svd(centered, full_matrices=False)
    tolerance = max(centered.shape) * t.finfo(t.float64).eps * singular[0].item()
    rank = int((singular > tolerance).sum())
    residual = D - (D @ vh[:rank].T) @ vh[:rank]
    energy = D.square().sum().item()
    radius = centered.square().sum(1).mean().sqrt().item()
    norms = t.linalg.vector_norm(D, dim=1)
    ratios = norms / radius if radius != 0 else None
    interior = (before > -1) & (before < 1); boundary = (before == -1) | (before == 1)
    after_interior = (after > -1) & (after < 1); after_boundary = (after == -1) | (after == 1)
    # Same-origin difference in the frozen clipped .01 internal proxy. No claim about realized EEF motion.
    proxy = .01 * t.cumsum(a.clamp(-1, 1) - b.clamp(-1, 1), dim=1)
    raw_cumulative = t.cumsum(d, dim=1)
    rb = t.linalg.vector_norm((b[:, 1:] - b[:, :-1]).reshape(16, 21), dim=1)
    ra = t.linalg.vector_norm((a[:, 1:] - a[:, :-1]).reshape(16, 21), dim=1)
    return {'native_dtype': str(before.dtype), 'summary_arithmetic': 'CPU float64 from native saved values; not CUDA replay',
        'sample_unit': 'particle-call; all 16 rows', 'rows': 16, 'components': 384,
        'before_support': support(before), 'after_support': support(after),
        'interior_to_boundary': int((interior & after_boundary).sum()),
        'boundary_to_interior': int((boundary & after_interior).sum()),
        'before_norm': distribution(t.linalg.vector_norm(B, dim=1)),
        'after_norm': distribution(t.linalg.vector_norm(a.reshape(16, 24), dim=1)),
        'assigned_delta_norm': distribution(norms), 'proposed_operand_norm': distribution(t.linalg.vector_norm(p.reshape(16, 24), dim=1)),
        'assigned_nonzero_components': int((d != 0).sum()),
        'before_centered_rms_radius': radius, 'delta_norm_over_radius': distribution(ratios) if ratios is not None else None,
        'zero_spread': radius == 0, 'centered_singular_values': singular.tolist(),
        'numerical_rank_tolerance': tolerance, 'numerical_rank': rank,
        'delta_energy_outside_centered_row_span_fraction': residual.square().sum().item() / energy if energy != 0 else None,
        'zero_delta_energy': energy == 0,
        'roughness_before': distribution(rb), 'roughness_after': distribution(ra), 'roughness_change': distribution(ra-rb),
        'raw_cumulative_prefix_difference_normalized_units': distribution(t.linalg.vector_norm(raw_cumulative, dim=2)),
        'clipped_internal_proxy_difference_m': distribution(t.linalg.vector_norm(proxy, dim=2)),
        'clipped_internal_proxy_endpoint_difference_m': distribution(t.linalg.vector_norm(proxy[:, -1], dim=1)),
        'per_row': [{'row': i, 'assigned_delta_norm': norms[i].item(),
                     'delta_norm_over_radius': ratios[i].item() if ratios is not None else None} for i in range(16)]}


def lineage_stats(before, after, child, operand):
    t = TORCH
    summary = describe(after, child, operand)
    b, a, c = [x.detach().to(t.float64).reshape(16, 24) for x in (before, after, child)]
    u = a-b; post_to_child = c-a; pre_to_child = c-b
    summary['observed_post_parent_to_child_inner_product_with_update'] = distribution((post_to_child*u).sum(1))
    summary['observed_pre_parent_to_child_inner_product_with_update'] = distribution((pre_to_child*u).sum(1))
    summary['observed_pre_parent_to_child_norm'] = distribution(t.linalg.vector_norm(pre_to_child, dim=1))
    summary['interpretation'] = 'one treated path; includes original noise/model/mask; no causal survival/attenuation ratio'
    # Do not label a parent→child difference as the actually applied mutation.
    summary['observed_post_parent_to_child_norm'] = summary.pop('assigned_delta_norm')
    summary['observed_post_parent_to_child_nonzero_components'] = summary.pop('assigned_nonzero_components')
    summary['observed_post_parent_to_child_norm_over_parent_radius'] = summary.pop('delta_norm_over_radius')
    summary['observed_post_parent_to_child_energy_outside_parent_row_span_fraction'] = summary.pop('delta_energy_outside_centered_row_span_fraction')
    summary.pop('per_row'); summary.pop('proposed_operand_norm')
    return summary


def check_storage(payload):
    t = TORCH; seen = set(); objects = set(); total = 0; visits = 0
    def walk(x):
        nonlocal total, visits
        visits += 1; require(visits <= 1000000, 'object count cap')
        if id(x) in objects: return
        objects.add(id(x))
        if t.is_tensor(x):
            require(x.device.type == 'cpu', 'non-CPU decoded storage')
            s=x.untyped_storage(); key=(s.data_ptr(),s.nbytes())
            if key not in seen: seen.add(key); total += s.nbytes()
            require(total <= CAP, 'decoded storage cap')
        elif isinstance(x, dict):
            for v in x.values(): walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x: walk(v)
        else: require(isinstance(x,(str,int,float,bool,type(None))), 'unexpected decoded object')
    walk(payload); return total


def cell_summary(payload, cell):
    t=TORCH; require(payload.get('schema')=='qd-ed-decision-evidence-v1','bundle schema')
    events=payload['events']; expected=cell['index_events']
    require([{k:e[k] for k in INDEX_KEYS} for e in events]==expected,'index identity mismatch')
    seq={e['sequence']:e for e in events};require(len(seq)==len(events),'duplicate sequence')
    identity=cell['first_identity'];require(all(e['decision_id']==identity['decision_id'] and e['global_step']==identity['global_step'] for e in events),'cross-decision')
    profile=cell['profile']; kind='n28_rbf_witness' if profile=='N28' else 'n27_rbf_witness'
    witnesses=[e for e in events if e['event']==kind]; calls=cell['witness_call_identities']
    require(len(witnesses)==len(calls)==11,'missing/extra witness')
    result={'task_id':cell['task_id'],'profile':profile,'attempt_id':cell['attempt_id'],'decision_id':identity['decision_id'],
            'status':'COMPLETE','calls':[],'missing':[], 'native_content_replay':False}
    for event, call in zip(witnesses,calls):
        v=event['values'];meta=v['metadata']; tensors=v['tensors'];stored=meta['call']
        require(meta.get('schema')==('n28-bounded-rbf-witness-v1' if profile=='N28' else 'n27-bounded-rbf-witness-v1') and meta.get('exact_cuda_replay_claim') is False,'witness schema/provenance')
        require(all(stored.get(k)==value for k,value in call.items()),'witness call identity')
        phase=call['phase'];iteration=call['iteration'];parent=profile=='N28' and phase=='parent'
        before_name='parent_offspring_before' if parent else 'model_output_before'
        after_name='parent_offspring_after' if parent else 'model_output_after'
        before=tensors[before_name];after=tensors[after_name];operand=tensors['update_operand']
        for name,value in [(before_name,before),(after_name,after),('update_operand',operand)]:
            info=meta['tensors'][name];require(info['shape']==list(value.shape) and info['dtype']==str(value.dtype),'declared shape/dtype mismatch')
        require(t.equal(before.contiguous().view(t.uint8),tensors['input_xyz'].contiguous().view(t.uint8)),'input/before binding')
        output={'phase':phase,'iteration':iteration,'denoising_step':call.get('denoising_step'),
                'sequence':event['sequence'],'update':describe(before,after,operand)}
        if parent:
            # Core metadata or numeric binding failures invalidate this cell, never invent a fallback mapping.
            allocation=seq[call['parent_allocation_sequence']];av=allocation['values'];require(allocation['event']=='parent_allocation' and av['iter_idx']==iteration and av['elite_count']==0,'allocation identity')
            selected=av['source_population'].index_select(0,av['parent_indices'])[:,:8,39:42]
            require(t.equal(selected.contiguous().view(t.uint8),before.contiguous().view(t.uint8)),'pre-parent bytes differ')
            boundary=seq[event['sequence']+1];bm=boundary['values']['metadata']
            require(boundary['event']=='n28_parent_renoise_input' and bm['parent_witness_sequence']==event['sequence'] and bm['parent_allocation_sequence']==allocation['sequence'] and bm['iteration']==iteration,'renoise identity')
            require(t.equal(boundary['values']['prefix'].contiguous().view(t.uint8),after.contiguous().view(t.uint8)),'post-parent/entry bytes differ')
            canonical=[x for x in identity['canonical_sources'] if x['iter_idx']==iteration]
            if len(canonical)!=1 or canonical[0]['canonical_sequence'] not in seq:
                output['parent_to_child']={'status':'UNKNOWN','reason':'exact canonical reference missing'}
            else:
                child_event=seq[canonical[0]['canonical_sequence']];cv=child_event['values']
                require(child_event['event']=='canonical_candidate_batch' and cv['iter_idx']==iteration,'canonical identity')
                require(cv['occurrence_ids']==[f"{identity['decision_id']}:q{child_event['sequence']}:r{i}" for i in range(16)],'child row identities')
                child=finite_tensor(cv['candidates'],(16,64,128))[:,:8,39:42]
                output['parent_to_child']={'status':'OBSERVED_ROW_LINEAGE','row_mapping_basis':'frozen no-elite original source order plus original audit; not untreated causal pairing',
                    'canonical_sequence':child_event['sequence'],'summary':lineage_stats(before,after,child,operand)}
        result['calls'].append(output)
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--release',type=Path,required=True);args=ap.parse_args()
    rb,rhash=read_bound(args.release,1024*1024);release=json.loads(rb)
    require(release.get('schema')=='n28-numerical-lineage-execution-release-v1' and release.get('execution_authorized')=='CPU_NUMERICAL_LINEAGE_ONLY','reader not released')
    review_bytes,_=read_bound(release['root_review']['path'],1024*1024,release['root_review']['sha256'])
    review=json.loads(review_bytes)
    require(review.get('schema')=='n28-numerical-lineage-preparation-root-review-v1' and review.get('decision')=='ACCEPT_PREPARATION_ONLY','root review required')
    require(all(review.get(k)==release.get(k) for k in ('reader_sha256','protocol_sha256','input_bindings_sha256')),'root review/code/input binding differs')
    for key,expected in [('cpu_seconds',120),('wall_seconds',120),('as_bytes',8*1024**3),('threads',2),('max_bundles',8)]:
        require(release['limits'].get(key)==expected,'resource release differs')
    read_bound(__file__,1024*1024,release['reader_sha256'])
    read_bound(HERE/'protocol-v1.md',1024*1024,release['protocol_sha256'])
    mb,mhash=read_bound(HERE/'input-bindings.frozen.v1.json',16*1024*1024,release['input_bindings_sha256']);manifest=json.loads(mb)
    cells=manifest['cells'];require([(x['task_id'],x['profile']) for x in cells]==[(i,p) for i in range(4) for p in ('N27','N28')],'fixed eight-cell coverage')
    require(sum(c['bundle']['bytes'] for c in cells)<=PAYLOAD_TOTAL_CAP,'frozen total payload cap')
    output=HERE/'execution-v1';output.mkdir(exist_ok=True)
    write_new(output/'run.started.json',{'release_sha256':rhash,'input_bindings_sha256':mhash,'started_unix':time.time()})
    os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1')
    cpus=sorted(os.sched_getaffinity(0));require(len(cpus)>=2,'two CPU affinity unavailable');os.sched_setaffinity(0,cpus[:2])
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));resource.setrlimit(resource.RLIMIT_CPU,(115,120))
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('internal wall bound')));signal.setitimer(signal.ITIMER_REAL,max(.001,115-(time.monotonic()-START)))
    tmp=output/'tmp';tmp.mkdir(exist_ok=True);tempfile.tempdir=str(tmp);sys.dont_write_bytecode=True
    denied=install_guard([args.release,release['root_review']['path'],HERE/'protocol-v1.md',HERE/'input-bindings.frozen.v1.json',__file__]+[x['bundle']['path'] for x in cells],output)
    report={'schema':'n28-closed-numerical-lineage-result-v1','complete':False,'cells':[], 'payload_reads':[], 'dependency_warnings':'external console log; not independently captured here',
            'interpretation':'unblinded descriptive CPU summaries; empirical span is not model prior manifold/uncertainty; no efficacy gate'}
    global TORCH
    try:
        import torch
        TORCH=torch;torch.set_num_threads(2);torch.set_num_interop_threads(1);require(not torch.cuda.is_initialized(),'CUDA initialized')
        total=0;decoded=0;zip_total=0
        for cell in cells:
            if not cell['first_guided_available']:
                report['cells'].append({'task_id':cell['task_id'],'profile':cell['profile'],'status':'UNKNOWN','reason':'first-guided binding unavailable; no backfill'});continue
            p=Path(cell['bundle']['path']);require(not p.is_symlink(),'bundle symlink')
            entry={'path':str(p),'sha256':None,'bytes':None,'read_count':None,'status':'READ_ATTEMPT_STARTED; failed-read byte/count may remain Unknown'}
            report['payload_reads'].append(entry)
            data,digest=read_bound(p,CAP,cell['bundle']['sha256']);entry.update(sha256=digest,bytes=len(data),read_count=1,status='HASH_VERIFIED')
            require(len(data)==cell['bundle']['bytes'],'frozen bundle size differs');total+=len(data);require(total<=PAYLOAD_TOTAL_CAP,'total payload cap')
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                infos=z.infolist();require(len(infos)<=50000 and all(not i.flag_bits&1 for i in infos),'ZIP entries/encryption cap')
                expanded=sum(i.file_size for i in infos);require(expanded<=CAP,'ZIP expansion cap');zip_total+=expanded;require(zip_total<=DECODED_TOTAL_CAP,'total ZIP expansion cap')
            payload=torch.load(io.BytesIO(data),map_location='cpu',weights_only=True);size=check_storage(payload);decoded+=size;require(decoded<=DECODED_TOTAL_CAP,'total decoded storage cap');entry.update(zip_uncompressed_bytes=expanded,decoded_storage_bytes=size)
            try:
                report['cells'].append(cell_summary(payload,cell))
            except (KeyError,ValueError,IndexError) as exc:
                report['cells'].append({'task_id':cell['task_id'],'profile':cell['profile'],'status':'INCOMPLETE','error_type':type(exc).__name__,'reason':str(exc)})
            del payload,data
            write_new(output/f"cell-{cell['task_id']}-{cell['profile']}.json",report['cells'][-1])
        require(not torch.cuda.is_initialized(),'CUDA initialized after CPU analysis')
        report['complete']=len(report['cells'])==8 and all(c['status']=='COMPLETE' for c in report['cells'])
    except Exception as exc:
        report['failure']={'type':type(exc).__name__,'reason':str(exc)}
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        report['resource']={'process_cpu_seconds':time.process_time(),'reader_wall_seconds':time.monotonic()-START,
            'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'rlimit_as_bytes':8*1024**3,
            'affinity':sorted(os.sched_getaffinity(0)),'denied_paths_or_operations':denied,
            'cuda_initialized':TORCH.cuda.is_initialized() if TORCH is not None else None,
            'external_wall_including_interpreter_start_exit_required':True}
        report['unread_cells']=[{'task_id':c['task_id'],'profile':c['profile']} for c in cells if not any(x['task_id']==c['task_id'] and x['profile']==c['profile'] for x in report['cells'])]
        write_new(output/'result-v1.json',report)
    return 0 if report['complete'] and not denied else 1


if __name__=='__main__':
    raise SystemExit(main())
