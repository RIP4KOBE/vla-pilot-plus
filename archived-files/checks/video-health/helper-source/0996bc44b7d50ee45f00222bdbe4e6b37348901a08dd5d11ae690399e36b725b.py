#!/usr/bin/env python3
"""Incrementally index/decode terminal videos; delivery evidence, not a scientific gate."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from fractions import Fraction

os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent/'video-health'
PIN='33954ead452927fc3168efb610487a688f89169e'
MODES=('eds','vls','eds_qd')


def sha(data):return hashlib.sha256(data).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def read(path):return json.loads(path.read_bytes())
def write(path,value):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');tmp.replace(path)
def now():return datetime.now(timezone.utc).isoformat()
def rows(path):
    raw=path.read_bytes();out=[];lines=raw.splitlines()
    for i,line in enumerate(lines):
        if not line.strip():continue
        try:value=json.loads(line)
        except ValueError:
            if i==len(lines)-1 and not raw.endswith(b'\n'):break
            raise
        out.append(value)
    return out

def guard(run,manifest):
    if manifest['commit']!=PIN:raise ValueError('Unexpected frozen commit')
    for rel,expected in manifest['source_sha256'].items():
        for base in (ROOT,run/'source'):
            path=(base/rel).resolve()
            if not path.is_relative_to(base.resolve()) or sha(path.read_bytes())!=expected:
                raise ValueError('Frozen source changed: '+str(path))
    for name,field in [('resolved-config.yaml','config_sha256'),('environment.json','environment_sha256'),('local-config.yaml','local_config_sha256')]:
        if sha((run/name).read_bytes())!=manifest[field]:raise ValueError('Run identity changed: '+name)
    return dict(commit=PIN,source_files=len(manifest['source_sha256']),source_hashes_sha256=sha(canonical(manifest['source_sha256'])))

def run_tool(argv):
    result=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=120,check=False)
    return dict(argv=argv,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)

def probe_video(video,action_count):
    probe=run_tool(['/usr/bin/ffprobe','-v','error','-select_streams','v','-count_frames','-show_entries',
        'stream=codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,nb_read_frames,duration:format=duration,size',
        '-of','json',str(video)])
    decode=run_tool(['/usr/bin/ffmpeg','-v','error','-xerror','-nostdin','-nostats','-err_detect','explode',
        '-hwaccel','none','-threads','1','-i',str(video),'-map','0:v:0','-progress','pipe:1','-f','null','-'])
    checks={'ffprobe_ok':probe['returncode']==0 and not probe['stderr'].strip(),
            'full_cpu_decode_ok':decode['returncode']==0 and not decode['stderr'].strip()}
    metadata={};parsed={}
    try:
        parsed=json.loads(probe['stdout']);streams=parsed['streams'];checks['one_video_stream']=len(streams)==1
        s=streams[0]
        width,height=int(s['width']),int(s['height']);fps=float(Fraction(s['avg_frame_rate']))
        frames=int(s['nb_read_frames']);container_frames=int(s['nb_frames']);duration=float(s.get('duration',parsed['format']['duration']))
        progress=dict(line.split('=',1) for line in decode['stdout'].splitlines() if '=' in line)
        decoded=int(progress.get('frame','-1'))
        checks.update(codec_h264=s.get('codec_name')=='h264',resolution_reasonable=64<=width<=4096 and 64<=height<=4096 and width%2==height%2==0,
            expected_fps_10=math.isclose(fps,10,rel_tol=0,abs_tol=1e-9),
            frame_counts_match_actions=frames==container_frames==decoded==action_count and frames>0,
            duration_matches_frames=math.isfinite(duration) and math.isclose(duration,frames/10,rel_tol=0,abs_tol=0.05),
            decode_reached_end=progress.get('progress')=='end')
        metadata=dict(codec=s.get('codec_name'),width=width,height=height,fps=fps,frame_count=frames,
                      container_frame_count=container_frames,full_decode_frame_count=decoded,duration_s=duration,action_count=action_count)
    except (ValueError,KeyError,TypeError,IndexError,ZeroDivisionError):checks['metadata_parseable']=False
    return dict(delivery_valid=all(checks.values()),checks=checks,metadata=metadata,ffprobe=probe,ffmpeg_cpu_decode=decode,parsed_probe=parsed)

def main():
    OUT.mkdir(exist_ok=True)
    versions={name:run_tool(['/usr/bin/'+name,'-version'])['stdout'].splitlines()[0] for name in ('ffprobe','ffmpeg')}
    all_reports=[];run_states={};pending=[]
    for mode in MODES:
        run=ROOT/'.worktrees/exp/steering-integration/runs'/f'{mode}-common-20261013'
        manifest=read(run/'manifest.json');status=read(run/'status.json');source=guard(run,manifest)
        if manifest['method']!=mode:raise ValueError('Wrong cohort method')
        run_states[mode]=status['state'];evaluation=run/manifest['evaluation_directory']
        compute=rows(evaluation/'episode_compute.jsonl');actions=rows(evaluation/'safety_events.jsonl')
        for episode,(task,seed) in enumerate(zip(manifest['tasks'],manifest['seeds'])):
            cs=[c for c in compute if c.get('episode_id')==episode or c.get('task_id')==task]
            if len(cs)>1:raise ValueError('Duplicate/conflicting completed compute')
            if not cs or cs[0].get('outcome')!='completed':
                pending.append(dict(method=mode,task_id=task,reason='episode_not_completed'));continue
            videos=list((run/'output'/f'episode_{episode+1}').glob('*agentview.mp4'))
            if len(videos)!=1 or not videos[0].is_file() or videos[0].stat().st_size==0:
                pending.append(dict(method=mode,task_id=task,reason='terminal_video_not_unique_nonempty'));continue
            video=videos[0]
            if video.name not in (f'episode_{episode+1}_success_agentview.mp4',f'episode_{episode+1}_fail_agentview.mp4'):
                raise ValueError('Not a normal terminal video: '+str(video))
            aa=[a for a in actions if a.get('event')=='stage_grasp_guard_action' and (a.get('episode')==episode or a.get('task_id')==task)]
            inputs=dict(video_sha256=sha(video.read_bytes()),compute_sha256=sha(canonical(cs[0])),actions_sha256=sha(canonical(aa)))
            destination=OUT/f'{mode}-task{task}.json'
            if destination.exists():
                report=read(destination)
                if report['inputs']!=inputs:raise ValueError('Previously indexed completed video/evidence changed: '+str(video))
            else:
                report=probe_video(video,len(aa))
                report['checks'].update(manifest_compute_seed=(cs[0].get('episode_id'),cs[0].get('task_id'),cs[0].get('episode_seed'))==(episode,task,seed),
                    action_identities=bool(aa) and all((a.get('episode'),a.get('task_id'))==(episode,task) for a in aa),
                    contiguous_action_steps=[a.get('global_step') for a in aa]==list(range(len(aa))),
                    raw_video_unchanged=sha(video.read_bytes())==inputs['video_sha256'])
                report.update(schema='steering_video_delivery_audit_v1',generated_at=now(),method=mode,task_id=task,episode=episode,seed=seed,
                    delivery_valid=all(report['checks'].values()),cohort_scientific_validity=None,
                    outcome='success' if '_success_' in video.name else 'failure',
                    video_path=str(video),video_relative_path=str(video.relative_to(run)),bytes=video.stat().st_size,
                    inputs=inputs,source=source,source_after=guard(run,manifest),tools=versions,helper_sha256=sha(Path(__file__).read_bytes()),
                    limits=['Delivery integrity only; not a new scientific validity or integration acceptance gate.',
                        'All frames are CPU decoded; semantic content and annotation correctness are not inferred from decode success.',
                        'Recorder adds one frame before each adapter step; expected frame count is joined to the frozen action log.',
                        'Resolution sanity range is 64..4096 pixels per axis with even dimensions; exact dimensions are reported.',
                        'Action logs have episode/task identity; seed is bound indirectly through the completed compute/manifest.'])
                write(destination,report)
                print(json.dumps(dict(event='video_audited',method=mode,task_id=task,delivery_valid=report['delivery_valid'],metadata=report['metadata'],
                    failed_checks=[k for k,v in report['checks'].items() if not v])),flush=True)
            all_reports.append((destination,report))
    summary=dict(schema='steering_video_delivery_index_v1',updated_at=now(),commit=PIN,run_states=run_states,
        helper_sha256=sha(Path(__file__).read_bytes()),tools=versions,indexed_count=len(all_reports),expected_total=30,
        all_indexed_delivery_valid=bool(all_reports) and all(r['delivery_valid'] for _,r in all_reports),
        all_30_videos_indexed=len(all_reports)==30,all_cohorts_finished=all(v=='finished' for v in run_states.values()),
        scientific_validity_affected=False,integration_acceptance=None,pending=pending,
        videos=[dict(method=r['method'],task_id=r['task_id'],seed=r['seed'],outcome=r['outcome'],video_path=r['video_path'],
                     video_relative_path=r['video_relative_path'],video_sha256=r['inputs']['video_sha256'],
                     delivery_valid=r['delivery_valid'],**r['metadata'],report_path=str(p),report_sha256=sha(p.read_bytes())) for p,r in all_reports])
    write(OUT/'index.json',summary)
    md=['# Terminal video delivery index','',f"Indexed {len(all_reports)}/30; delivery checks {'pass' if summary['all_indexed_delivery_valid'] else 'failed'}. Remaining videos are pending.",'',
        'These checks do not alter scientific validity, outcomes, or the integration acceptance gate.','',
        '| Method | Task | Outcome | Frames | Resolution | Duration | Delivery | Video |','|---|---:|---|---:|---|---:|---|---|']
    for _,r in all_reports:
        m=r['metadata'];md.append(f"| {r['method']} | {r['task_id']} | {r['outcome']} | {m.get('frame_count','?')} | {m.get('width','?')}×{m.get('height','?')} | {m.get('duration_s','?')} s | {'PASS' if r['delivery_valid'] else 'FAIL'} | [agentview]({r['video_path']}) |")
    (OUT/'index.md').write_text('\n'.join(md)+'\n')
    print(json.dumps(dict(event='video_index',indexed_count=len(all_reports),delivery_valid=summary['all_indexed_delivery_valid'],path=str(OUT/'index.json'))),flush=True)
    return 0 if summary['all_indexed_delivery_valid'] else 1

if __name__=='__main__':raise SystemExit(main())
