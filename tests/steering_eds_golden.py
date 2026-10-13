#!/usr/bin/env python3
"""Frozen EDS CPU differential harness. All writes stay in --output-dir.

The only scientific code executed is loaded from explicit --source-root.
No checkpoint, simulator or service runs. Use a fresh subprocess for suite isolation.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import gzip
import importlib.metadata
import json
import logging
import os
from pathlib import Path
import random
import sys
from types import ModuleType, SimpleNamespace
from typing import Optional, Union

os.environ.update(CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1',
                  HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                  OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONNOUSERSITE='1')
sys.dont_write_bytecode = True


def audit_guard(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'subprocess.Popen', 'os.system'}:
        raise RuntimeError('Offline golden harness forbids network/process calls: '+event)


sys.addaudithook(audit_guard)
import numpy as np
import torch
import yaml
from diffusers import DPMSolverMultistepScheduler
from torch import nn

HERE = Path(__file__).resolve().parent
torch.set_num_threads(1)
torch.set_num_interop_threads(1)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def read_json(path):
    data=path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix=='.gz' else data)


def tensor_record(value, values=False):
    value = value.detach().cpu().contiguous()
    result = {'shape': list(value.shape), 'dtype': str(value.dtype),
              'sha256': sha(value.reshape(-1).view(torch.uint8).numpy().tobytes())}
    if values:
        result['values'] = value.tolist()
    return result


def rng_record():
    npstate = np.random.get_state()
    return {'python': sha(canonical(random.getstate())),
            'numpy': sha(canonical([npstate[0],npstate[1].tolist(),*npstate[2:]])),
            'torch_cpu': tensor_record(torch.get_rng_state())['sha256']}


def extract_method(path, cls_name, method_name, namespace):
    tree = ast.parse(path.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls_name)
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method_name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[method_name]


def load_runtime(root):
    # Avoid importing simulator/provider-heavy package initializers, as the
    # existing RDT unit tests do. Concrete scientific submodules remain real.
    for name in ('core','utils'):
        mod = ModuleType(name); mod.__path__ = [str(root/name)]; sys.modules[name] = mod
    envmod = ModuleType('core.env_adapters'); envmod.BaseEnvAdapter = object
    envmod.__path__ = [str(root/'core/env_adapters')]; sys.modules[envmod.__name__] = envmod
    from core.rdt_policy_steer import RDTSteer
    from core.stage_evidence import parse_observation
    from core.stage_grasp_guard import apply_to_action
    from core.target_distance_reward import reference
    projection = extract_method(root/'core/env_adapters/libero_adapter.py', 'LiberoAdapter',
        'delta_actions_to_ee_trajectory', {'torch':torch,'np':np,'Union':Union})
    dispatch = extract_method(root/'main.py','Main','_update_stage',
        {'Optional':Optional,'np':np,'log':logging.getLogger('golden.main')})
    return RDTSteer, parse_observation, apply_to_action, reference, projection, dispatch


class FakeAdapter:
    """Controlled sensor fixture; action-dependent motion between fixed anchors.

    Chunk anchors deliberately exercise controller branches. They are not claimed
    as simulated physics or real success. The projection itself is source code.
    """
    _env_config = {'vlm_camera':'agentview'}

    def __init__(self):
        self.position = np.array([0.,0.,.5],dtype=np.float64)
        self.step_number = 0

    def anchor(self, step):
        self.step_number = step
        self.position = np.array([0. if step == 0 else .38,0.,.5],dtype=np.float64)

    def get_ee_pose_world(self):
        return SimpleNamespace(position=self.position.copy())

    def get_task_description(self):
        return 'pick up the red block and place it in the basket'

    def get_vlm_image(self):
        a=np.zeros((128,128,3),dtype=np.uint8); a[20:45,40:65,0]=220
        a[70:90,65:110,1]=160; return a

    def get_camera_params(self, name):
        return SimpleNamespace(width=128,height=128,
            intrinsic=np.array([[60.,0.,64.],[0.,60.,64.],[0.,0.,1.]]),
            extrinsic=np.eye(4))

    def get_obs(self):
        return {'agentview_image':self.get_vlm_image(),
                'robot0_eye_in_hand_image':np.full((128,128,3),50,dtype=np.uint8),
                'robot0_joint_pos':np.array([.1,-.2,.8,0.,0.,0.,.04],dtype=np.float32),
                'robot0_gripper_qpos':np.array([.02,.02],dtype=np.float32),
                'task':self.get_task_description()}

    def step(self, action):
        self.position += .01 * action.detach().cpu().numpy()[:3].astype(np.float64)
        self.step_number += 1


class CheapDiT(nn.Module):
    def __init__(self, dtype, adapter):
        super().__init__(); self.marker=nn.Parameter(torch.zeros((),dtype=dtype),requires_grad=False)
        self.adapter=adapter

    def forward(self, x, t, cond):
        out=.18*torch.tanh(x)
        out[:,:,39] += .08
        out[:,:,40] -= .03
        out[:,:,10] = .25 if self.adapter.step_number < 144 else -.25
        return out


class CheapModel(nn.Module):
    def __init__(self, dtype, adapter):
        super().__init__(); self.dit=CheapDiT(dtype,adapter); self.encode_calls=0
        # Exact constructor kwargs from the frozen RDT runner/checkpoint config.
        self.noise_scheduler=DPMSolverMultistepScheduler(num_train_timesteps=1000,
            beta_schedule='squaredcos_cap_v2',prediction_type='sample')
        self._real=SimpleNamespace(encode_instruction=lambda task,device:torch.ones(1,1,4096),
                                   vision_model=None,text_model=None)

    def encode_inputs(self, state, state_mask, images, text):
        self.encode_calls += 1
        mask=torch.zeros_like(state_mask,dtype=torch.float32)
        mask[0,[39,40,41,42,43,44,10]]=1.
        return {'lang_cond':torch.ones(1,1,4),'lang_attn_mask':torch.ones(1,1,dtype=torch.bool),
                'img_cond':torch.ones(1,1,4),'state_traj':torch.zeros(1,1,4),
                'action_mask':mask.unsqueeze(1),'ctrl_freqs':torch.tensor([20]),
                'action_indices':[39,40,41,42,43,44,10],'unified_action_dim':128}


def instrument(policy, context, record):
    def wrap(name, observer):
        original=getattr(policy,name)
        def call(*args,**kwargs):
            return observer(original,args,kwargs)
        setattr(policy,name,call)

    def point(): return dict(context)

    def parent(original,args,kwargs):
        before=rng_record(); result=original(*args,**kwargs)
        population,costs,_=args
        record['parents'].append({**point(),'rng_before':before,'rng_after':rng_record(),
            'population':tensor_record(population),'costs':tensor_record(costs,True),
            'offspring_indices':result.offspring_parent_indices.tolist(),
            'elite_indices':result.elite_indices.tolist(),
            'selected_parent_tensor':tensor_record(population.index_select(0,result.offspring_parent_indices)),
            'sources':list(result.offspring_sources),'info':result.info})
        return result
    wrap('_eds_select_parent_plan',parent)

    def renoise(original,args,kwargs):
        before=rng_record(); inp=tensor_record(args[0]); result=original(*args,**kwargs)
        record['renoise'].append({**point(),'input':inp,'steps':int(args[1]),
            'output':tensor_record(result),'rng_before':before,'rng_after':rng_record()})
        return result
    wrap('_eds_renoise_reference',renoise)

    def score(original,args,kwargs):
        before=rng_record(); result=original(*args,**kwargs)
        record['scores'].append({**point(),'population':tensor_record(args[0]),
            'costs':tensor_record(result[0],True),'rng_before':before,'rng_after':rng_record()})
        return result
    wrap('_eds_score_population_as_cost',score)

    def reward(original,args,kwargs):
        result=original(*args,**kwargs)
        row={'keypoints':tensor_record(args[1]),'trajectory':tensor_record(args[2]),
             'value':tensor_record(result,True) if torch.is_tensor(result) else float(result)}
        record['reward_receipts'].append({**point(),**row})
        return result
    wrap('_counted_reward',reward)

    def postprocess(original,args,kwargs):
        result=original(*args,**kwargs)
        record['decoded'].append({**point(),'selected_latent':tensor_record(args[0]),
                                  'actions':tensor_record(result,True)})
        return result
    wrap('_postprocess_actions',postprocess)

    def reset_observer(name):
        def observer(original,args,kwargs):
            before={'reference':policy._stage_init_reward,'raw':policy._last_raw_reward,
                    'progress':policy.get_normalized_reward(),'rng':rng_record()}
            result=original(*args,**kwargs)
            record['resets'].append({**point(),'method':name,'args':list(args),'before':before,
                'after':{'reference':policy._stage_init_reward,'raw':policy._last_raw_reward,
                         'progress':policy.get_normalized_reward(),'rng':rng_record()}})
            return result
        return observer
    for name in ('reset','reset_stage','reset_eds_chunk_memory'):
        wrap(name,reset_observer(name))


def clean(value, output):
    if isinstance(value,dict):
        return {str(k):clean(v,output) for k,v in value.items()
                if not str(k).endswith(('latency_s','duration_s')) and k!='raw_png_path'}
    if isinstance(value,(tuple,list)): return [clean(v,output) for v in value]
    if isinstance(value,str): return value.replace(str(output),'$OUTPUT')
    if isinstance(value,np.generic): return value.item()
    if torch.is_tensor(value): return tensor_record(value,True)
    return value


def _run_scenario(root, output, dtype_name, runtime):
    RDTSteer,parse_observation,apply_action,reference,projection,dispatch=runtime
    dtype=getattr(torch,dtype_name)
    cfg=yaml.safe_load((root/'configs/evaluation/libero_object_swap.yaml').read_text())
    cfg['main']['eds_eval']['output_dir']=str(output/dtype_name)
    eds_config=dict(cfg['main']['eds_config'])
    eds_config.update(reward_mode=cfg['main']['eds_eval']['reward_mode'],
                      shuffle_seed=cfg['main']['eds_eval']['shuffle_seed'],
                      mechanism_pretest=dict(cfg['main']['eds_mechanism_pretest']))
    # Only output location changes. Model weights/env/provider are replaced by
    # fixtures; policy hyperparameters and online controller flags stay frozen.
    adapter=FakeAdapter(); adapter.delta_actions_to_ee_trajectory=projection.__get__(adapter)
    model=CheapModel(dtype,adapter); policy=RDTSteer(model,num_inference_steps=5)
    policy.post_init(adapter,None,20,cfg['policy']['rdt'])
    context={'dtype':dtype_name,'episode':0,'step':-1}
    rec={k:[] for k in ('parents','renoise','scores','reward_receipts','decoded','resets',
                        'stage','queries','actions','chunks','episode_totals')}
    instrument(policy,context,rec)
    points=np.array([[.4,0.,.5],[.7,-.15,.45],[.9,.15,.60]],dtype=np.float32)
    def reaching(kp,path): return reference(kp,path,0)
    def zero(kp,path): return path.new_tensor(0.)
    runner=SimpleNamespace(config=cfg['main'],backend='libero',policy_type='rdt',policy=policy,
        adapter=adapter,stage_live_keypoints=points,keypoint_id_to_object={0:'red_block_1_main',1:'basket_1_low',2:'basket_1_high'},
        guidance_fns={1:[reaching],2:[zero]},stage_descriptions='Synthetic reach then transport fixture',
        init_img_with_keypoints=None,_append_stage_event=rec['stage'].append,
        _append_safety_event=lambda event:None)
    recognizer=SimpleNamespace(last_result=None)
    def observe(**kwargs):
        step=context['step']
        observation={'target_visibility':'clear','target_location':'outside_goal',
                     'grasp':'held' if 96<=step<128 else 'not_held',
                     'support':'unsupported' if 96<=step<128 else 'supported',
                     'evidence':'Deterministic synthetic provider response for CPU parity.'}
        result=parse_observation(json.dumps(observation))
        recognizer.last_result={'ok':True,'observation':result,'raw_response':json.dumps(observation)}
        rec['queries'].append({**context,'trigger':kwargs['trigger_reason'],
                              'image_sha256':sha(kwargs['current_rgb'].tobytes()),'observation':result})
        return result
    recognizer.observe_scene=observe; runner.gemini_stage_recognizer=recognizer
    safety=[]; runner._append_safety_event=safety.append
    # Independent seeds are CPU test stimuli, not production RNG fixtures.
    for episode,length in ((0,160),(1,16)):
        seed=90210+episode
        random.seed(seed);np.random.seed(seed);torch.random.default_generator.manual_seed(seed)
        context.update(episode=episode,step=-1)
        policy.reset();policy.set_eds_episode_context(episode,seed)
        state={'current_stage':1,'use_guidance':True,'global_step':0,'vlm_query_count':0,
               'episode_id':episode,'task_id':0,'episode_seed':seed,'chunk_id':0}
        previous=None
        for step in range(length):
            context['step']=step;adapter.step_number=step
            fresh=step%8==0
            state.update(global_step=step,chunk_id=step//8)
            if fresh:
                adapter.anchor(step)
                before=rng_record()
                dispatch(runner,state,previous,.8,.6)
                after=rng_record()
                if before!=after: raise AssertionError('Stage/probe/mock service consumed CPU RNG')
            before=rng_record(); before_counts=policy.get_episode_compute_counters()
            actions=policy.select_action(batch=adapter.get_obs(),generate_new_chunk=fresh,
                use_guidance=state['use_guidance'],keypoints=points,
                guidance_fns=runner.guidance_fns[state['current_stage']] if state['use_guidance'] else None,
                guidance_type='eds',vls_config=cfg['main']['vls_config'],eds_config=eds_config,
                global_step=step,current_stage=state['current_stage'])
            raw=actions[0,step%8].clone()
            actions=apply_action(runner,state,actions,step%8,step)
            executed=actions[0,step%8]
            if not torch.equal(raw,executed): raise AssertionError('Frozen action passthrough changed')
            after=rng_record(); after_counts=policy.get_episode_compute_counters()
            if not fresh and (before!=after or before_counts!=after_counts):
                raise AssertionError('Cached action consumed RNG/compute')
            row={**context,'fresh':fresh,'stage':state['current_stage'],'guided':state['use_guidance'],
                 'action':tensor_record(executed,True),'chunk':tensor_record(actions),
                 'cache_remaining':policy._cached_action_steps_remaining,
                 'reference':policy._stage_init_reward,'raw_reward':policy._last_raw_reward,
                 'progress':policy.get_normalized_reward(),'rng_before':before,'rng_after':after}
            rec['actions'].append(row)
            if fresh:
                trace=policy.get_last_eds_mechanism_trace()
                trace_rows=[] if trace is None else [dict(stage=t.stage,iter_idx=t.iter_idx,
                    actions=tensor_record(t.actions),trajectories=tensor_record(t.trajectories),
                    rewards=tensor_record(t.rewards,True),costs=tensor_record(t.costs,True),
                    parent_indices=None if t.parent_indices is None else t.parent_indices.tolist())
                    for t in trace.stages]
                rec['chunks'].append({**context,'stage_state':dict(state),'counters':after_counts,
                    'reference':policy._stage_init_reward,'raw_reward':policy._last_raw_reward,
                    'progress':policy.get_normalized_reward(),'metrics':policy.get_last_eds_metrics(),
                    'rng':after,'encoder_calls':model.encode_calls,'mechanism_trace':trace_rows})
            adapter.step(executed);previous=float(executed[-1])
        rec['episode_totals'].append({'episode':episode,'length':length,
            'counters':policy.get_episode_compute_counters(),'rng':rng_record()})
    rec['safety']=safety
    return clean(rec,output)


def run_scenario(root, output, dtype_name, runtime):
    saved=(random.getstate(),np.random.get_state(),torch.get_rng_state().clone())
    before=rng_record()
    try:
        return _run_scenario(root,output,dtype_name,runtime)
    finally:
        random.setstate(saved[0]);np.random.set_state(saved[1]);torch.set_rng_state(saved[2])
        assert rng_record()==before,'Golden harness leaked CPU RNG state'


def validate_coverage(behavior):
    result={}
    for dtype,r in behavior['scenarios'].items():
        chunks={(x['episode'],x['step']):x for x in r['chunks']}
        c=lambda step:chunks[(0,step)]
        assert c(8)['progress']>=.8
        assert c(16)['stage_state']['contact_phase']=='contact_grace'
        assert not c(16)['stage_state']['use_guidance']
        assert c(80)['stage_state']['use_guidance']
        assert c(0)['reference']==c(16)['reference']==c(80)['reference']
        assert c(96)['stage_state']['current_stage']==2 and c(96)['reference'] is None
        assert c(128)['stage_state']['current_stage']==1 and c(128)['progress']==0
        assert chunks[(1,0)]['progress']==0
        guided=[x for x in r['chunks'] if x['stage_state']['use_guidance']]
        assert len(guided)==10
        for x in guided:
            m=x['metrics']
            assert m['population_size_observed']==16 and m['eds_iters_executed']==10
            assert m['initial_diversity_steps']==4 and m['rollout_diversity_iters_applied']==10
            assert not m['qd_archive_enabled']
            assert x['mechanism_trace']
            assert not any(v for k,v in m.items() if k.endswith('fallback_used'))
            assert [it['n_trunc_steps'] for it in m['per_iter']]==[3,2,2,2,2,1,1,1,1,1]
        assert len(r['parents'])==len(r['renoise'])==100
        # Main also enables mechanism diagnostics: they score intermediate
        # populations in addition to the 11 search batches per guided chunk.
        assert sum(x['metrics']['score_call_count'] for x in guided)==110
        assert len(r['scores'])==sum(x['counters']['reward_scoring_batches'] for x in r['episode_totals'])
        assert len(r['reward_receipts'])==sum(x['counters']['reward_calls'] for x in r['episode_totals'])
        assert len(r['scores'])>110
        for parent,noise in zip(r['parents'],r['renoise']):
            assert parent['selected_parent_tensor']==noise['input']
            assert len(parent['offspring_indices'])==16 and not parent['elite_indices']
        assert all(x['trajectory']['shape']==[1,7,3] for x in r['reward_receipts'])
        assert not any(x['override'] for x in r['safety'])
        assert all(x['raw_action']==x['executed_action'] for x in r['safety'])
        assert len(r['actions'])==176 and len(r['safety'])==176
        assert {x['action']['values'][-1] for x in r['actions']}=={-1.,1.}
        for episode in (0,1):
            group=[x for x in r['actions'] if x['episode']==episode]
            for i in range(0,len(group),8):
                block=group[i:i+8]
                assert len({x['chunk']['sha256'] for x in block})==1
                assert [x['cache_remaining'] for x in block]==list(range(7,-1,-1))
                assert sum(x['fresh'] for x in block)==1
        result[dtype]={'passed':True,'actions':176,'chunks':len(r['chunks']),
            'guided_chunks':len(guided),'parent_draw_batches':100,'search_score_batches':110,
            'actual_score_batches_including_diagnostics':len(r['scores']),
            'actual_reward_calls':len(r['reward_receipts']),
            'real_stage_grace_start':16,'grace_expiry':80,'stage2':96,'stage1_recovery':128}
    return result


def mismatch(a,b,path='$'):
    if type(a)!=type(b):return path+': types differ'
    if isinstance(a,dict):
        if set(a)!=set(b):return path+': keys differ '+str(sorted(set(a)^set(b)))
        for key in a:
            issue=mismatch(a[key],b[key],path+'.'+key)
            if issue:return issue
    elif isinstance(a,list):
        if len(a)!=len(b):return path+': lengths differ'
        for i,(x,y) in enumerate(zip(a,b)):
            issue=mismatch(x,y,f'{path}[{i}]')
            if issue:return issue
    elif a!=b:return path+': values differ'
    return None


def main():
    p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True)
    p.add_argument('--provenance',type=Path,default=HERE/'source-provenance.json')
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--compare',type=Path)
    args=p.parse_args();root=args.source_root.resolve();out=args.output_dir.resolve()
    if out.exists():p.error('Output directory must be new')
    out.mkdir(parents=True)
    provenance=json.loads(args.provenance.read_text())
    source_before={f['path']:sha((root/f['path']).read_bytes()) for f in provenance['files']}
    runtime=load_runtime(root)
    logging.disable(logging.CRITICAL)
    behavior={'schema':'eds_cpu_golden_behavior_v1',
              'scenarios':{name:run_scenario(root,out,name,runtime) for name in ('float32','bfloat16')}}
    coverage=validate_coverage(behavior)
    source_after={rel:sha((root/rel).read_bytes()) for rel in source_before}
    assert source_before==source_after,'Runtime source changed during capture'
    assert not torch.cuda.is_initialized(),'CUDA was initialized'
    text=json.dumps(behavior,indent=2,allow_nan=False)+'\n'
    (out/'behavior.json').write_text(text)
    packed=gzip.compress(text.encode(),mtime=0)
    (out/'behavior.json.gz').write_bytes(packed)
    difference=mismatch(read_json(args.compare),behavior) if args.compare else None
    report={'kind':'synthetic_cpu_frozen_algorithm_reference_not_performance',
            'behavior_sha256':sha(text.encode()),'source_sha256':source_before,
            'behavior_gzip_sha256':sha(packed),
            'source_unchanged':True,'cuda_initialized':False,'network_and_subprocess_guard':True,
            'scenario_cpu_rng_restored':True,
            'distribution_metadata':{n:importlib.metadata.version(n) for n in ('torch','numpy','diffusers','Pillow','PyYAML','opencv-python-headless')},
            'actual_module_versions':{name:getattr(sys.modules[name],'__version__',None)
                for name in ('torch','numpy','diffusers','PIL','yaml','cv2')},
            'cpu_threads':torch.get_num_threads(),'cpu_interop_threads':torch.get_num_interop_threads(),
            'python':sys.version,'harness_sha256':sha(Path(__file__).read_bytes()),
            'coverage':coverage,
            'comparison_requested':args.compare is not None,'comparison_difference':difference}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'output':str(out),'behavior_sha256':report['behavior_sha256'],
                     'comparison_difference':difference,'cuda_initialized':False}))
    if difference:raise SystemExit(1)


if __name__=='__main__':main()
