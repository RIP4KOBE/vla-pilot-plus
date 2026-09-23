#!/usr/bin/env python3
"""Decode only the approved fixed grid; no simulator, model, OCR or image repair."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import PIL
from PIL import Image, ImageDraw, ImageFont

A=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
W=Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
BASE=A/'continuation_20260923/n2-dev-v1'
HEAD='525506ca3198f54d86dadf84bbb76eb64926d87a'
AUTH_SHA='f488d1b66f624a27eea3bf887e20e9c5029e6ba50837e7bab94e9337b09c450f'
GRID=[0,8,16,24,32,64,96,128,160,240,320,400,480,560,640,719]
ARMS=['C0','Q0','N2']
IDS=[
 'rdt-qd-ed-final-20260921T093925Z__n2_dev_t00_c0_20260923__3cc1e46f83d0',
 'rdt-qd-ed-final-20260921T093925Z__n2_dev_t00_q0_recovery1_20260923__28dd3c7a9e74',
 'rdt-qd-ed-final-20260921T093925Z__n2_dev_t00_n2_20260923__45c5f8694f85']
NUMERIC=BASE/'explanatory-read-v1/output-v1'
SEQUENCE_SHA='b8a7c7bce23975ff1f421c7e7cd87eccc7d2517549301f4a81fb34189d1affa4'
PROVENANCE_SHA='dfddb2ff80734cabf7a819beef213ded8ab3410a02cc0a6b49ebced48fe70910'
FRESH_SHA={
 'C0':'aaec9b206c9b55d20399b69fa67812ab7b3041a518f6743f3132be87839f32f7',
 'Q0':'28bd13d7d722ba377e26e17dbbc826d623f34debf04a35577a19e582cee8bdc8',
 'N2':'c2d233cdb7fa1b9af1493f414f407ddecd73c21a007dc5e98a5c63b75da4feae'}


def require(value, reason):
    if not value: raise ValueError(reason)


def sha(data): return hashlib.sha256(data).hexdigest()


def selection_filter(grid):
    require(grid==GRID, 'unapproved_frame_grid')
    return 'select=' + '+'.join(f'eq(n\\,{n})' for n in grid)


def caption_context(arm, index):
    matches=[d for d in arm['decisions'] if d['global_step']<=index<=d['last_executed_step']]
    require(len(matches)==1, 'missing_or_ambiguous_caption_context')
    d=matches[0]
    return {'decision_id':d['decision_id'],'stage':d['stage'],'use_guidance':d['use_guidance'],
        'meaning':'recorded decision state active before this action; not a new visual classification'}


def decoded_count(stderr):
    counts=re.findall(r'Input stream #0:0 \(video\):[^\n]*?(\d+) frames decoded',stderr)
    require(len(counts)==1, 'decoded_frame_count_unavailable_or_ambiguous')
    return int(counts[0])


def cell_position(row,column):
    require(0<=row<3 and 0<=column<4, 'invalid_sheet_cell')
    return 12+column*(480+12),12+row*(480+56+12)


def xjson(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def run(args):
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','empty_CUDA_mask_required')
    require('torch' not in sys.modules,'torch_not_needed_in_extractor')
    hashes={}
    def read(path,expected):
        path=Path(path);require(not path.is_symlink(),'symlink_input')
        b=path.read_bytes();require(sha(b)==expected,'hash_mismatch:'+str(path))
        hashes[str(path)]=expected;return b
    auth=json.loads(read(args.authorization,AUTH_SHA))
    require(auth['authorized'] is True and auth['CPU_only'] is True and auth['frame_ordinals_per_arm']==GRID
        and auth['total_exported_frames']==48 and auth['contact_sheet_pages']==4,'authorization_contract_mismatch')
    freeze=json.loads(args.freeze.read_bytes())
    require(freeze['status']=='CPU_TESTED_FROZEN_BEFORE_FIRST_DECODE','not_frozen')
    require(sha(Path(__file__).read_bytes())==freeze['source_sha256'],'extractor_changed_after_freeze')
    hashes[str(args.freeze)]=sha(args.freeze.read_bytes())
    for ref in freeze['files']: read(ref['path'],ref['sha256'])
    require(PIL.__version__==freeze['tools']['Pillow'],'Pillow_version_changed')
    ffmpeg=freeze['tools']['ffmpeg'];font_path=freeze['tools']['font']
    read(ffmpeg,freeze['tools']['ffmpeg_sha256']);read(font_path,freeze['tools']['font_sha256'])
    bound={name:read(ref['path'],ref['sha256']) for name,ref in auth['bound_inputs'].items()}
    inventory=json.loads(bound['visual-inventory-v1.json'])
    mapping=json.loads(bound['source-frame-mapping-v1.json'])
    require(inventory['exact_attempts']==IDS and mapping['proposed_selection']['indices']==GRID,'inventory_scope_mismatch')
    require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip()==HEAD,'production_HEAD_changed')
    for ref in inventory['sources']: read(ref['path'],ref['sha256'])
    for ref in inventory['capture_configuration']: read(ref['path'],ref['sha256'])
    sequence=json.loads(read(NUMERIC/'closed-loop-sequence.json',SEQUENCE_SHA))
    provenance=json.loads(read(NUMERIC/'inputs-and-audit.json',PROVENANCE_SHA))
    require(provenance['source_commit']==HEAD and [a['attempt_id'] for a in sequence['arms']]==IDS,'numeric_scope_mismatch')
    videos=[v for v in inventory['files'] if v['kind']=='video']
    require(len(videos)==3 and [v['arm'] for v in videos]==ARMS,'video_scope_mismatch')
    admissions=[]
    for arm,name,v in zip(ARMS,IDS,videos):
        root=A/'attempts'/name
        require(Path(v['path'])==root/'episode_1/episode_1_fail_agentview.mp4','video_path_mismatch')
        read(v['path'],v['sha256'])
        terminal_path=root/'attempt-result.json';audit_path=root/'eds_eval/decision-evidence-audit.json'
        terminal=json.loads(read(terminal_path,provenance['input_sha256'][str(terminal_path)]))
        original=json.loads(read(audit_path,provenance['input_sha256'][str(audit_path)]))
        fresh=json.loads(read(NUMERIC/(arm.lower()+'-fresh-audit.json'),FRESH_SHA[arm]))
        require(terminal['attempt_id']==name and terminal['outcome_valid'] is True and terminal['source_commit']==HEAD,'terminal_not_accepted')
        require(all(a['accepted'] is True and a['evidence_complete'] is True and not a['errors'] for a in [original,fresh]),'audit_not_accepted')
        streams=v['container_metadata']['streams']
        require(len(streams)==1 and streams[0]['codec_type']=='video' and streams[0]['nb_frames']=='720'
            and streams[0]['width']==640 and streams[0]['height']==640 and streams[0]['avg_frame_rate']=='10/1','video_container_contract_mismatch')
        admissions.append({'arm':arm,'attempt_id':name,'terminal_sha256':hashes[str(terminal_path)],
            'original_audit_sha256':hashes[str(audit_path)],'fresh_audit_sha256':FRESH_SHA[arm],
            'complete_current_audit_reused_by_hash':True,'tensor_audit_rerun':False})
    out=args.output
    require(out.resolve().is_relative_to(BASE/'visual-read-v1'),'output_outside_authorized_directory')
    out.mkdir(exist_ok=False)
    xjson(out/'verified-inputs-before-decode.json',{'source_commit':HEAD,'inputs':hashes,'admissions':admissions,
        'source_sha256':freeze['source_sha256'],'selected_grid':GRID,'pixel_decode_started':False})
    frame_rows=[];decode_records=[]
    frame_bytes=640*640*3
    for v,armdata in zip(videos,sequence['arms']):
        arm=v['arm'];dest=out/arm.lower();dest.mkdir()
        command=[ffmpeg,'-hide_banner','-nostdin','-loglevel','verbose','-hwaccel','none','-threads','1',
            '-i',v['path'],'-map','0:v:0','-an','-sn','-dn','-filter_threads','1','-vf',selection_filter(GRID),
            '-fps_mode','passthrough','-c:v','rawvideo','-pix_fmt','rgb24','-threads:v','1','-f','rawvideo','pipe:1']
        result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={**os.environ,'CUDA_VISIBLE_DEVICES':''},timeout=180)
        log=result.stderr.decode('utf-8',errors='replace')
        logpath=out/(arm.lower()+'-decode-metadata.txt')
        with logpath.open('x') as f:f.write(log)
        require(result.returncode==0,'software_decode_failed:'+arm)
        count=decoded_count(log)
        require(count==720,'decoded_count_mismatch:'+arm)
        require(len(result.stdout)==len(GRID)*frame_bytes,'selected_frame_payload_count_or_shape_mismatch:'+arm)
        for i,index in enumerate(GRID):
            data=result.stdout[i*frame_bytes:(i+1)*frame_bytes]
            image=Image.frombytes('RGB',(640,640),data)
            path=dest/f'frame_{index:06d}.png'
            with path.open('xb') as f:image.save(f,format='PNG')
            frame_rows.append({'arm':arm,'parent_video':v['path'],'parent_video_sha256':v['sha256'],
                'presentation_frame_index':index,'presentation_time_seconds':index/10,'action_relation':'before_action',
                'action_global_step':index,'completed_episode_actions_before_frame':index,'warmup_steps_excluded':5,
                'raw_decoded_rgb_sha256':sha(data),'png_path':str(path),'png_sha256':sha(path.read_bytes()),
                'shape':[640,640,3],'dtype':'uint8','caption_context':caption_context(armdata,index)})
        decode_records.append({'arm':arm,'command':command,'returncode':result.returncode,'decoded_frame_count':count,
            'exported_frame_count':len(GRID),'raw_rgb_bytes':len(result.stdout),'decode_log_sha256':sha(logpath.read_bytes()),
            'hardware_acceleration':'none','nonselected_frame_export_or_inspection':False})
        print(json.dumps({'arm':arm,'decoded_frame_count':count,'selected_frames':len(GRID),'GPU':False}),flush=True)
    require(len(frame_rows)==48,'total_frame_count_mismatch')
    sheets=[];font=ImageFont.truetype(font_path,18)
    for page in range(4):
        sheet=Image.new('RGB',(1980,1656),'white');draw=ImageDraw.Draw(sheet);cells=[]
        for row,arm in enumerate(ARMS):
            for col,index in enumerate(GRID[page*4:(page+1)*4]):
                record=next(r for r in frame_rows if r['arm']==arm and r['presentation_frame_index']==index)
                x,y=cell_position(row,col)
                with Image.open(record['png_path']) as im:
                    require(im.size==(640,640) and im.mode=='RGB','selected_png_shape_changed')
                    tile=im.resize((480,480),Image.Resampling.LANCZOS)
                    sheet.paste(tile,(x,y))
                ctx=record['caption_context'];name='Q0 recovery1' if arm=='Q0' else arm
                draw.text((x,y+484),f'{name} | frame {index} | before action {index}',font=font,fill='black')
                draw.text((x,y+507),f"Recorded Stage {ctx['stage']} | Guide {'ON' if ctx['use_guidance'] else 'OFF'}",font=font,fill='black')
                cells.append({'row':row,'column':col,'arm':arm,'frame':index,'image_origin_xy':[x,y],
                    'image_size':[480,480],'png_sha256':record['png_sha256']})
        path=out/f'contact-sheet-{page+1:02d}.png'
        with path.open('xb') as f:sheet.save(f,format='PNG')
        sheets.append({'path':str(path),'sha256':sha(path.read_bytes()),'size':[1980,1656],
            'cells':cells,'transform':'full uncropped frame, uniform0.75 scale, Pillow LANCZOS; external caption below image'})
    require(all(sha(Path(path).read_bytes())==digest for path,digest in hashes.items()),'input_changed_during_decode')
    require('torch' not in sys.modules,'unexpected_torch_import')
    manifest={'schema':'task0-fixed-grid-video-extraction-v1','source_commit':HEAD,'authorization_sha256':AUTH_SHA,
        'freeze_sha256':sha(args.freeze.read_bytes()),'source_sha256':freeze['source_sha256'],'tools':freeze['tools'],
        'admissions':admissions,'input_sha256':hashes,'decoded':decode_records,'frames':frame_rows,'sheets':sheets,
        'frame_grid':GRID,'total_exported_frames':len(frame_rows),'contact_sheet_pages':len(sheets),
        'visual_inspection_status':'NOT_YET_VIEWED_AT_EXTRACTION_COMPLETION','GPU_model_provider_projector_simulator_OCR_calls':0,
        'python_torch_imported':False,'CUDA_VISIBLE_DEVICES':os.environ['CUDA_VISIBLE_DEVICES'],
        'limitations':['source-before-action mapping; last action response absent','Step/Stage/Guide visual consistency pending authorized sheet review',
            'prediction overlays are not executed motion','outcome labels retroactively stamped on every frame','no contact/grasp/target/causal inference']}
    xjson(out/'decode-manifest-v1.json',manifest)
    print(json.dumps({'output':str(out),'manifest_sha256':sha((out/'decode-manifest-v1.json').read_bytes()),
        'sheet_paths_sha256':{s['path']:s['sha256'] for s in sheets}}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--authorization',type=Path,required=True)
    p.add_argument('--freeze',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    run(p.parse_args())
