"""Small independent serializer-shaped JSON fixtures; no experiment readers."""
import copy
import hashlib
import json
from pathlib import Path
from scalar_summary_v1 import COMMIT,COHORT,REVIEW_READER_SHA,NORMS

def metric(arm,step=0,zero=False):
    def call(phase,i,j):
        initial=phase=='initial';z=zero or (arm=='N26' and (not initial or j==0))
        clipped=192 if arm=='N26' and initial else 0 if arm=='N26' else 96
        boundary=0 if arm=='N26' and initial else 384 if arm=='N26' else 48
        norm=0. if z else float([1,2,3,4][j] if arm=='N25' and initial else [0,2,4,6][j] if initial else 2)
        v={'schema':arm.lower()+'-rbf-call-summary-v1','descriptor_mode':'actuator_clipped_eef_v1',
         'source':'core.qd_clean_output_rbf:model_output_sample_v1' if arm=='N26' else 'core.qd_actuator_clipped_rbf:clipped_rbf_gradient:v1',
         'absolute_fallback_used':False,'summary_only_not_exact_replay':True,'input_shape':[16,64,128],
         'input_dtype':'torch.bfloat16','input_stride':[8576,128,1] if arm=='N26' else [8192,128,1],
         'horizon':8,'translation_indices':[39,40,41],'translation_components':384,
         'update_operand_is_measured_output_delta':False,'clipped_components':clipped,'boundary_components':boundary,
         'interior_components':384-clipped-boundary,'nonfinite_count':0,'zero_gradient':z,
         'phase':phase,'iteration':i,'denoising_step':j,'timestep':100-j,'global_step':step,'stage':1}
        if arm=='N26':v.update(input_source='model_output_sample_v1',prediction_type='sample',input_binding='same_forward_unmodified_model_output',model_jacobian_used=False)
        for k in NORMS:
            value=norm if k=='gradient_before_normalization' else 0. if z else 20. if k=='update_operand' else 1.
            v[k]={'finite':True,'zero':z,'norm':value,'norm_dtype':'torch.bfloat16'}
        return v
    m={'global_step':step,'initial_diversity_descriptor_mode':'actuator_clipped_eef_v1','rollout_diversity_descriptor_mode':'actuator_clipped_eef_v1',
      'initial_diversity_steps':4,'rollout_diversity_steps_applied':15,'initial_direction_rbf_evidence_by_step':[call('initial',-1,j) for j in range(4)],
      'rollout_direction_rbf_evidence_by_iter':[],'rollout_rbf_steps_by_iter':[]}
    for i,length in enumerate((3,2,2,2,2,1,1,1,1,1)):
        indices=list(range(2 if length>1 else 1))
        m['rollout_direction_rbf_evidence_by_iter'].append([call('rollout',i,j) for j in indices])
        m['rollout_rbf_steps_by_iter'].append({'n_trunc_steps':length,'iter_idx':i,'step_indices':indices,
          'step_flags':[j in indices for j in range(length)],'step_count':len(indices),'fallback_used':False})
    return m

class Fixture:
    def __init__(self,root,n=7,all_zero_guided=False):
        self.root=Path(root);self.root.mkdir(exist_ok=True);self.files=[];self.values={};self.refs={}
        source_files=[{'path':f'core/static_{i:03}.py','sha256':'a'*64} for i in range(315)]
        canonical=json.dumps(source_files,sort_keys=True,separators=(',',':')).encode()
        self.put('source',{'commit':COMMIT,'files':source_files,'sha256':hashlib.sha256(canonical).hexdigest()})
        rows=[{'episode_key':f't{t}-{a}','task_id':t,'profile':a} for t in range(10) for a in ('C0','Q0','N25','N26')]
        self.put('plan',{'source_commit':COMMIT,'code_files':source_files,'episodes':rows})
        cells=[];attempts=[];original=[];bindings=[]
        counts={a:{'audited':0,'success':0} for a in ('C0','Q0','N25','N26')}
        native={a:{'guided_decisions':0,'all_call_summaries_verified':0,'zero_gradient_calls':0,'clipped_components':0} for a in ('C0','Q0','N25','N26')}
        for row in rows[:n]:
            arm=row['profile'];aid='synthetic-'+row['episode_key'];directory=self.root/'attempts'/aid
            refs={r:{'path':str(directory/(r+'.json')),'sha256':'b'*64} for r in ('audit','context','receipt','terminal')}
            guided=arm in ('N25','N26') and row['task_id']==0 and not all_zero_guided
            if arm in ('N25','N26'):
                p=directory/'eds_metrics.jsonl'
                reference=self.put('metrics',[metric(arm)] if guided else None,p)
                refs['metrics']=reference;bindings.append({'attempt_id':aid,'ref':reference})
                if guided:
                    native[arm].update(guided_decisions=1,all_call_summaries_verified=19,
                        zero_gradient_calls=16 if arm=='N26' else 0,clipped_components=768 if arm=='N26' else 1824)
            cell={**row,'attempt_id':aid,'success':False,'audit':refs['audit'],'worker_context':refs['context'],'worker_receipt':refs['receipt'],'attempt_result':refs['terminal']}
            cells.append(cell);counts[arm]['audited']+=1;original.append({'attempt_id':aid,'refs':refs})
            attempts.append({'attempt_id':aid,'terminal':{'outcome_valid':True,'episode_key':row['episode_key'],
                'guided_chunks':int(guided),'rbf_gradient_calls':19 if guided else 0,'rbf_gradient_batch_rows':304 if guided else 0}})
        self.put('result',{'schema':'n26-dev-cohort-result-v1','cohort_id':COHORT,'source_commit':COMMIT,'decision':'INVALID_OR_INTERRUPTED',
            'plan':self.refs['plan'],'planned':40,'audited_cells':n,'accepted_cells':cells,'counts':counts,'native':native,'attempts':attempts})
        self.put('terminal_input',{'schema':'n26-terminal-metadata-input-v1','root_authorized':True,'executable':True,
          'refs':{k:self.refs[k] for k in ('result','plan','source')},'attempts':original,'files':copy.deepcopy([x for x in self.files if x['role']=='metrics'])})
        self.put('terminal_review',{'schema':'n26-root-terminal-review-v1','decision':'ACCEPT_TERMINAL_RECONSTRUCTION',
            'discrepancies':[],'unsettled_attempts':[],'cohort_disposition':'INVALID_OR_INTERRUPTED',
            'reader':{'path':str(self.root/'terminal_reader_v1.py'),'sha256':REVIEW_READER_SHA},
            **{k:self.refs[k] for k in ('result','plan','source')},'input_manifest':self.refs['terminal_input'],
            'accepted_cells':n,'counts':counts,'native':native})
        self.data={'schema':'n26-scalar-summary-input-v1','root_authorized':True,'executable':True,
           'refs':self.refs,'files':self.files,'metrics':bindings}
    def put(self,role,value,path=None):
        p=Path(path) if path else self.root/(role+'.json');p.parent.mkdir(parents=True,exist_ok=True)
        if value is None:b=None
        else:
            b=(''.join(json.dumps(x,allow_nan=False)+'\n' for x in value) if p.suffix=='.jsonl' else json.dumps(value,allow_nan=False)).encode();p.write_bytes(b)
        reference={'path':str(p),'sha256':hashlib.sha256(b).hexdigest() if b is not None else None}
        r={'role':role,**reference,'bytes':len(b) if b is not None else 0,'present':b is not None}
        old=next((i for i,x in enumerate(self.files) if x['path']==str(p)),None)
        if old is None:self.files.append(r)
        else:self.files[old]=r
        self.values[str(p)]=value
        if path is None:self.refs[role]=reference
        return reference
