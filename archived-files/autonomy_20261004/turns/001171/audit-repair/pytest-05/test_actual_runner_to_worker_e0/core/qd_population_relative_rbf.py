"""N29 native assignment/evidence; unchanged RBF and N28 operator placement."""
from types import SimpleNamespace
import json
import time
import torch
from core.qd_actuator_clipped_rbf import applied_evidence
from core.qd_clean_output_rbf import require_sample_scheduler
from core.qd_feasible_ray_rbf import observe as observe_box
from core.qd_parent_before_renoise import ParentWitness, validate_placement as validate_parent
from core.qd_population_relative_trust import population_relative_trust_update
MODE='population_relative_trust_v1'
PLACEMENT='parent_before_renoise_v1'
SOURCE='core.qd_population_relative_rbf:population_relative_trust_v1'
INPUT='current_chunk_selected_parent_offspring'
EXTRA={'scaled_operand':(16,8,3),'beta':(16,),'radius':(),'operand_norms':(16,)}


def validate_option(cfg):
    if getattr(cfg,'diversity_update_mode',None)!=MODE:
        raise ValueError('N29 requires explicit population-relative update')
    if getattr(cfg,'rollout_diversity_placement',None)!=PLACEMENT:
        raise ValueError('N29 requires N28 parent placement')
    prior=SimpleNamespace(**{**vars(cfg),'diversity_update_mode':'feasible_ray_v1'})
    validate_parent(prior)


def step(before,operand,cfg,scheduler):
    started=time.perf_counter();validate_option(cfg);require_sample_scheduler(cfg,scheduler)
    return population_relative_trust_update(before,operand),started


def observe(evidence,before,after,operand,result,started):
    # Reuse only old descriptive assignment checks on the actually scaled operand.
    # The returned evidence is explicitly N29; raw proposal remains separately bound.
    observe_box(evidence,before,after,result.scaled_operand,result.alpha,started)
    evidence.update(schema='n29-rbf-call-summary-v1',source=SOURCE,diversity_update_mode=MODE,
        update_operand_semantics='unconstrained_native_proposal_before_population_trust_and_feasible_ray',
        scaled_operand_semantics='native_cast_of_raw_times_fp32_row_beta_before_feasible_ray',
        radius_dtype='torch.float32',radius=float(result.radius),
        beta=[float(v) for v in result.beta.detach().cpu().tolist()],
        operand_norms=[float(v) for v in result.operand_norms.detach().cpu().tolist()],
        trust_limited_rows=int((result.beta<1).sum()),
        scaled_operand_norm_fp32=float(torch.norm(result.scaled_operand.float())),
        population_trust_overhead_seconds=max(0.,time.perf_counter()-started),
        radius_semantics='FP32 centered population RMS over rows; not calibrated uncertainty',
        exact_real_postcast_distance_bound_claim=False)


def capture_trust(capture,result):
    if capture is not None:
        for k in EXTRA:capture[k]=getattr(result,k).detach().clone()


def mutate(offspring, *, cfg, scheduler, compute_gradient, mask_gradient,
           witness, iteration, parent_allocation_sequence):
    """Mutate only the actual selected copy; no RNG/model/score calls."""
    validate_option(cfg)
    if cfg.rollout_diversity_placement != PLACEMENT:
        raise ValueError("N29 requires explicit parent placement")
    require_sample_scheduler(cfg, scheduler)
    if tuple(offspring.shape) != (16, 64, 128):
        raise ValueError("N29 requires 16 selected parent offspring")
    if type(iteration) is not int or not 0 <= iteration < 10:
        raise ValueError("N29 parent iteration outside fixed ten rounds")
    capture = witness.prepare("parent", iteration)
    gradient, evidence = compute_gradient(
        offspring, descriptor_mode=cfg.rollout_diversity_descriptor_mode,
        descriptor_cfg=cfg.__dict__,
        **({"capture_out": capture} if capture is not None else {}))
    if gradient is None or not bool(torch.isfinite(gradient).all()):
        raise ValueError("N29 missing/nonfinite parent gradient")
    masked = mask_gradient(gradient).to(device=offspring.device, dtype=offspring.dtype)
    operand = -1.0 * float(cfg.rollout_diversity_scale) * masked[:, :8, (39, 40, 41)]
    before = offspring[:, :8, (39, 40, 41)].detach().clone()
    started = time.perf_counter()
    feasible = population_relative_trust_update(before, operand)
    offspring[:, :8, (39, 40, 41)] = feasible.prefix
    after = offspring[:, :8, (39, 40, 41)]
    applied_evidence(evidence, masked=masked, update=operand, phase="parent",
                     iteration=iteration, step=None, timestep=None)
    observe(evidence, before, after, operand, feasible, started)
    evidence.update(schema="n29-parent-rbf-call-summary-v1", source=SOURCE,
        input_source=INPUT, input_binding="selected_offspring_before_original_renoise",
        rollout_diversity_placement=PLACEMENT, parent_allocation_sequence=parent_allocation_sequence,
        prediction_type="sample", model_jacobian_used=False,
        update_operand_semantics="unconstrained_native_parent_proposal_before_population_trust_and_feasible_ray",
        after_semantics="assigned_parent_offspring; not model output or final action",
        original_renoise_and_denoise_follow=True)
    if capture is not None:
        capture.update(update_operand=operand.detach().clone(),
                       parent_offspring_before=before,
                       parent_offspring_after=after.detach().clone())
        capture_trust(capture, feasible)
        witness.emit(capture, evidence)
        witness.pending_parent = (offspring, iteration, parent_allocation_sequence)
    return evidence

class TrustWitness(ParentWitness):
    SOURCE=SOURCE
    SCHEMA='n29-bounded-rbf-witness-v1'
    EVENT='n29_rbf_witness'
    COVERAGE_EVENT='n29_rbf_witness_coverage'

    def observe_renoise_input(self, offspring, steps):
            if self.pending_parent is None:
                return
            original, iteration, allocation = self.pending_parent
            if offspring is not original or steps != (3,2,2,2,2,1,1,1,1,1)[iteration]:
                raise ValueError("N29 actual renoise argument identity/schedule differs")
            prefix = offspring[:, :8, (39,40,41)].detach().clone()
            size = prefix.numel() * prefix.element_size()
            metadata = {"schema":"n29-parent-renoise-boundary-v1", "iteration":iteration,
                "parent_allocation_sequence":allocation, "parent_witness_sequence":self.parent_event_sequence,
                "n_trunc_steps":steps, "same_tensor_object_verified":True, "numeric_bytes":size,
                "observation":"actual _eds_renoise_reference entry before noise draw"}
            if (self.parent_numeric_bytes + size > self.NUMERIC_CALL_CAP
                    or self.numeric_bytes + size > self.NUMERIC_EPISODE_CAP
                    or self.parent_metadata_bytes + len(json.dumps(metadata).encode()) > self.METADATA_CALL_CAP):
                raise ValueError("N29 combined parent/boundary evidence cap")
            self.recorder.record("n29_parent_renoise_input", metadata=metadata, prefix=prefix)
            self.numeric_bytes += size
            self.pending_parent = None

    def emit(self,capture,evidence):
        if capture is None:return
        phase=evidence.get('phase');parent=phase=='parent'
        before='parent_offspring_before' if parent else 'model_output_before'
        after='parent_offspring_after' if parent else 'model_output_after'
        expected={'input_xyz','source_origins','cast_origins','projected_xyz','gradient_before',
                  'gradient_after','update_operand',before,after}|set(EXTRA)
        if (set(capture)!=expected or phase not in {'parent','initial'}
                or evidence.get('source')!=SOURCE or evidence.get('diversity_update_mode')!=MODE
                or evidence.get('schema')!=('n29-parent-rbf-call-summary-v1' if parent else 'n29-rbf-call-summary-v1')
                or evidence.get('input_source')!=(INPUT if parent else 'model_output_sample_v1')
                or evidence.get('input_binding')!=('selected_offspring_before_original_renoise' if parent else 'same_forward_unmodified_model_output')
                or evidence.get('prediction_type')!='sample' or evidence.get('model_jacobian_used') is not False):
            raise ValueError('N29 witness source/fields differ')
        if not self.active or self.recorder is None:raise ValueError('N29 witness outside selected decision')
        key=(phase,evidence['iteration'])
        if key not in self.seen or key in self.recorded or len(self.recorded)>=11:raise ValueError('N29 unselected/duplicate slot')
        for name,value in capture.items():
            shape=EXTRA.get(name,(16,3) if name in {'source_origins','cast_origins'} else (16,8,3))
            if not torch.is_tensor(value) or tuple(value.shape)!=shape or not bool(torch.isfinite(value).all()):
                raise ValueError('N29 witness shape/nonfinite')
        a,b=capture['input_xyz'],capture[before]
        if a.dtype!=b.dtype or a.device!=b.device or not torch.equal(a.contiguous().view(torch.uint8),b.contiguous().view(torch.uint8)):
            raise ValueError('N29 input/preassignment bytes differ')
        size=sum(t.numel()*t.element_size() for t in capture.values())
        if size>self.NUMERIC_CALL_CAP or self.numeric_bytes+size>self.NUMERIC_EPISODE_CAP:raise ValueError('N29 witness byte cap')
        meta={'schema':self.SCHEMA,'source':SOURCE,'call':dict(evidence),'numeric_bytes':size,
            'tensors':{n:{'dtype':str(t.dtype),'shape':list(t.shape),'capture_stride_before_serialization':list(t.stride())} for n,t in capture.items()},
            'identity_binding':'enclosing decision; same forward initial or actual parent allocation',
            'exact_cuda_replay_claim':False}
        meta_size=len(json.dumps(meta,allow_nan=False).encode())
        if meta_size>self.METADATA_CALL_CAP:raise ValueError('N29 metadata cap')
        seq=self.recorder.record(self.EVENT,metadata=meta,tensors=capture)
        if parent:self.parent_event_sequence=seq;self.parent_numeric_bytes=size;self.parent_metadata_bytes=meta_size
        self.numeric_bytes+=size;self.recorded.append(key)
