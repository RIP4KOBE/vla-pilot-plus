"""N27 explicit configuration, descriptive update evidence and bounded witness."""
import time
import torch
from core.qd_actuator_clipped_rbf import BoundedWitness, MODE as GEOMETRY
from core.qd_clean_output_rbf import CLEAN_SOURCE, require_sample_scheduler
from core.qd_feasible_ray_update import feasible_ray_update

LEGACY='legacy_additive'
MODE='feasible_ray_v1'
SOURCE='core.qd_feasible_ray_rbf:feasible_ray_v1'


def validate_update_option(cfg):
    mode=getattr(cfg,'diversity_update_mode',LEGACY)
    if mode not in {LEGACY,MODE}:raise ValueError('unsupported diversity_update_mode')
    if mode==LEGACY:return
    required={'diversity_input_source':CLEAN_SOURCE,'initial_diversity_descriptor_mode':GEOMETRY,
        'rollout_diversity_descriptor_mode':GEOMETRY,'population_size':16,'cem_iters':10,'num_elites':16,
        'initial_sampling_mode':'rbf_diverse_denoise','truncated_rollout_mode':'rbf_diverse',
        'initial_diversity_scale':20.,'initial_diversity_start_ratio':.8,
        'rollout_diversity_scale':20.,'rollout_diversity_start_ratio':.6,'rollout_diversity_iters':'all',
        'rollout_diversity_skip_final_steps':0,'rollout_diversity_control_mode':'fixed',
        'renoise_t_min':1,'renoise_t_max':3,'search_schedule_mode':'legacy_linear',
        'chunk_population_mode':'fresh'}
    for key,value in required.items():
        if getattr(cfg,key,None)!=value:raise ValueError('N27 requires '+key+'='+repr(value))


def step(before,operand,cfg,scheduler):
    started=time.perf_counter()
    validate_update_option(cfg)
    if cfg.diversity_update_mode!=MODE:raise ValueError('N27 step requires explicit opt-in')
    require_sample_scheduler(cfg,scheduler)
    return feasible_ray_update(before,operand),started


def observe(evidence,before,after,operand,alpha,started):
    """Observe the actual assigned prefix; raw operand is never renamed delta."""
    if (tuple(alpha.shape)!=(16,) or alpha.dtype!=torch.float32
            or not bool(torch.isfinite(alpha).all()) or not bool(((alpha>=0)&(alpha<=1)).all())):
        raise ValueError('N27 alpha evidence invalid')
    delta=after.detach().float()-before.detach().float()
    moving=operand!=0
    zero_preserved=torch.equal(after[~moving].contiguous().view(torch.uint8),before[~moving].contiguous().view(torch.uint8))
    outside_before=int(((before<-1)|(before>1)).sum().item())
    outside_after=int(((after<-1)|(after>1)).sum().item())
    support=not bool((moving&((before<=-1)|(before>=1))).any())
    if not support or not zero_preserved or outside_after!=outside_before:
        raise ValueError('N27 actual assignment violated feasible-prefix contract')
    evidence.update(schema='n27-rbf-call-summary-v1',source=SOURCE,diversity_update_mode=MODE,
        update_operand_semantics='unconstrained_native_proposal_before_feasible_ray',
        update_operand_is_measured_output_delta=False,alpha_dtype='torch.float32',
        alpha=[float(v) for v in alpha.detach().cpu().tolist()],limited_rows=int((alpha<1).sum().item()),
        before_outside_components=outside_before,after_outside_components=outside_after,
        strict_support_valid=True,zero_update_bytes_preserved=True,
        realized_nonzero_delta_components=int(torch.count_nonzero(delta).item()),
        realized_delta_norm_fp32=float(torch.norm(delta).item()),
        realized_delta_definition='assigned_after.float()-before.float(); not proposed operand',
        feasible_update_overhead_seconds=max(0.,time.perf_counter()-started),
        overhead_scope='host wall including helper, assignment and scalar synchronization; not CUDA-only latency')


class FeasibleRayWitness(BoundedWitness):
    SOURCE=SOURCE
    SCHEMA='n27-bounded-rbf-witness-v1'
    EVENT='n27_rbf_witness'
    COVERAGE_EVENT='n27_rbf_witness_coverage'

    def emit(self,capture,evidence):
        if capture is not None:
            if (evidence.get('schema')!='n27-rbf-call-summary-v1' or evidence.get('source')!=SOURCE
                    or evidence.get('input_source')!=CLEAN_SOURCE or evidence.get('prediction_type')!='sample'
                    or evidence.get('input_binding')!='same_forward_unmodified_model_output'
                    or evidence.get('model_jacobian_used') is not False
                    or evidence.get('update_operand_semantics')!='unconstrained_native_proposal_before_feasible_ray'):
                raise ValueError('N27 bounded witness semantic downgrade')
            a,b=capture.get('input_xyz'),capture.get('model_output_before')
            if (not torch.is_tensor(a) or not torch.is_tensor(b) or a.dtype!=b.dtype or a.device!=b.device
                    or a.shape!=b.shape or not torch.equal(a.contiguous().view(torch.uint8),b.contiguous().view(torch.uint8))):
                raise ValueError('N27 clean input/model-before bytes differ')
        super().emit(capture,evidence)
