#!/usr/bin/env python3
"""Frozen, single-input, 32-outcome rigid geometry calculation; stdlib only."""
import csv, hashlib, json, math, os, pathlib, resource, sys, time
START_CPU=time.process_time(); START_WALL=time.monotonic()
resource.setrlimit(resource.RLIMIT_CPU,(60,60))
D=pathlib.Path(__file__).resolve().parent
INPUT=D.parent/'approach-handoff-review-v1/decode-v1/result-v1.json'
EXPECTED='fd63df833c0839efd87ddea5d3ffcb75eebfe493730aef018f809d9937324f46'
ROWS=[]; ERROR=None

def vector(x,n):
    if not isinstance(x,dict) or x.get('shape') not in ([n],[1,n]): raise ValueError('missing/unsupported vector shape')
    v=x.get('values')
    if x['shape']==[1,n] and isinstance(v,list) and len(v)==1: v=v[0]
    if not isinstance(v,list) or len(v)!=n or any(type(z) not in (float,int) or not math.isfinite(z) for z in v): raise ValueError('invalid finite vector')
    return [float(z) for z in v]

def row_geometry(ep,dec,obs,target):
    row={'task_id':ep['task_id'],'step':obs['step'],'decision_start':dec['global_step'],'stage':dec.get('stage'),'use_guidance':dec.get('use_guidance'),'status':'Unknown','reason':None}
    try:
        p=vector(obs['eef_position'],3); q=vector(obs['eef_quaternion'],4); g=vector(obs['gripper_qpos'],2)
        norm=math.sqrt(math.fsum(v*v for v in q))
        if not math.isfinite(norm) or norm==0: raise ValueError('zero/nonfinite quaternion norm')
        x,y,z,w=[v/norm for v in q]
        R=[[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
           [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
           [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]]
        delta=[target[i]-p[i] for i in range(3)]
        a=[math.fsum(R[j][i]*delta[j] for j in range(3)) for i in range(3)]
        lower=g[1]+0.0005; upper=g[0]-0.0005; gap=upper-lower
        centered=[a[0],a[1]-(g[0]+g[1])/2,a[2]+0.0036]
        vx=max(abs(a[0])-0.008,0); vz=max(abs(centered[2])-0.008,0)
        vy=max(lower-a[1],a[1]-upper,0) if gap>=0 else None
        distance=math.sqrt(vx*vx+vy*vy+vz*vz) if vy is not None else None
        row.update(status='SOURCE_CALIBRATED_POINT_GEOMETRY',quaternion_norm_before_normalization=norm,
            target_hand_x_m=a[0],target_hand_y_m=a[1],target_hand_z_m=a[2],
            target_grip_site_x_m=-a[1],target_grip_site_y_m=a[0],target_grip_site_z_m=a[2],
            target_pad_center_x_m=centered[0],target_pad_center_y_m=centered[1],target_pad_center_z_m=centered[2],
            signed_inner_face_gap_m=gap,inner_face_lower_y_m=lower,inner_face_upper_y_m=upper,
            x_overlap_excess_m=vx,z_overlap_excess_m=vz,jaw_interval_excess_m=vy,
            point_to_inner_prism_distance_m=distance,
            point_in_inner_prism=(vx==0 and vy==0 and vz==0) if vy is not None else None,
            qpos_nominal_ranges_exceeded=not(0<=g[0]<=0.04 and -0.04<=g[1]<=0),
            eef_position_dtype=obs['eef_position'].get('dtype'),eef_quaternion_dtype=obs['eef_quaternion'].get('dtype'),gripper_qpos_dtype=obs['gripper_qpos'].get('dtype'),
            physical_capture='Unknown',current_object_geometry='Unknown')
    except (KeyError,ValueError,TypeError,OverflowError) as e: row['reason']=str(e)
    return row

try:
    assert sorted(os.sched_getaffinity(0))==[0,1] and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    raw=INPUT.read_bytes(); assert hashlib.sha256(raw).hexdigest()==EXPECTED
    data=json.loads(raw); assert data['complete'] is True and len(data['episodes'])==2
    assert [ep['task_id'] for ep in data['episodes']]==[0,1]
    for ep in data['episodes']:
        try: target=vector(ep['fixed_step16_target_snapshot'],3)
        except (KeyError,ValueError,TypeError): target=None
        assert [v['global_step'] for v in ep['decisions']]==[16,24]
        for dec in ep['decisions']:
            assert len(dec['observed_steps'])==8
            assert [v['step'] for v in dec['observed_steps']]==list(range(dec['global_step'],dec['global_step']+8))
            for obs in dec['observed_steps']:
                if target is None:
                    ROWS.append({'task_id':ep['task_id'],'step':obs['step'],'decision_start':dec['global_step'],'status':'Unknown','reason':'fixed target missing/invalid'})
                else: ROWS.append(row_geometry(ep,dec,obs,target))
    assert len(ROWS)==32
    summaries=[]
    for task in (0,1):
        for phase in (16,24):
            rs=[v for v in ROWS if v['task_id']==task and v['decision_start']==phase]
            good=[v for v in rs if v['status']!='Unknown']; summary={'task_id':task,'decision_start':phase,'rows':len(rs),'valid_rows':len(good)}
            for key in ('target_pad_center_x_m','target_pad_center_y_m','target_pad_center_z_m','signed_inner_face_gap_m','point_to_inner_prism_distance_m'):
                vs=[v[key] for v in good if v[key] is not None]; summary[key]={'min':min(vs),'max':max(vs),'mean':math.fsum(vs)/len(vs)} if vs else None
            summary['point_in_inner_prism_count']=sum(v.get('point_in_inner_prism') is True for v in good)
            summary['overlapping_pad_faces_count']=sum(v['signed_inner_face_gap_m']<0 for v in good)
            summaries.append(summary)
    result={'schema':'n30-fixed-capture-geometry-v1','complete':True,'input_sha256':EXPECTED,'arithmetic':'Python binary64 normalized rigid transform, not native arithmetic replay','target_semantics':'fixed step16 arbitrary perception keypoint, not current object pose or volume','runtime_geometry_binding':'current local Panda/PandaGripper source contract; historical instantiated XML not reread','rows':ROWS,'groups':summaries,'algorithm_nomination':None}
    with (D/'geometry-result-v1.json').open('x') as out: json.dump(result,out,indent=2,allow_nan=False);out.write('\n')
    fields=list(dict.fromkeys(k for row in ROWS for k in row))
    with (D/'geometry-table-v1.csv').open('x',newline='') as out:
        writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader();writer.writerows(ROWS)
    print(json.dumps({'complete':True,'rows':len(ROWS),'groups':summaries},allow_nan=False))
except BaseException as e:
    ERROR=type(e).__name__+': '+str(e)
    with (D/'geometry-partial-v1.json').open('x') as out:json.dump({'rows':ROWS,'error':ERROR},out,indent=2)
    print(ERROR,file=sys.stderr)
finally:
    receipt={'schema':'n30-fixed-geometry-resource-v1','complete':ERROR is None,'error':ERROR,'pid':os.getpid(),'affinity':sorted(os.sched_getaffinity(0)),'threads':2,'cpu_seconds':time.process_time()-START_CPU,'wall_seconds':time.monotonic()-START_WALL,'input_json_reads':1,'tensor_video_reads':0,'production_imports':False,'gpu_model_api_sim_calls':0,'automatic_retries':0,'rows_completed':len(ROWS),'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    with (D/'geometry-resource-v1.json').open('x') as out:json.dump(receipt,out,indent=2);out.write('\n')
if ERROR:sys.exit(1)
