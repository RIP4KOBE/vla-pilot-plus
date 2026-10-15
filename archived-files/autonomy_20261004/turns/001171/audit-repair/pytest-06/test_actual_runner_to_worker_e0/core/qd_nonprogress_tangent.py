"""N36 independent one-boundary executed-open nonprogress memory. No replay or forced selection.

Occurrence IDs are transported by QDArchive, never recovered from hashes.
The optional observer is passive; missing physical trigger fields mean ineligible,
whereas contradictory occurrence/decode/ack records raise and reset the state.
"""
from dataclasses import dataclass
import copy
import math
import torch
from core.qd_capture_dwell import native_id
from core.qd_capture_dwell_proposal import _same_native_bytes as same, _native, _geometry_vector, CaptureDwellProposal
from core.rdt_libero_action_converter import encode_libero_prefix
from core.qd_observed_jaw_approach import ObservedJawDecision, MODE as N34_MODE, SOURCE_FILES as N34_SOURCES
from core.rdt_libero_action_converter import decode_rdt_libero_action_chunk

MODE = 'nonprogress_tangent_v1'
SOURCE_FILES = N34_SOURCES + ('core/qd_nonprogress_tangent.py',)
CONTINUITY = ('episode', 'stage', 'provider', 'target_index', 'tracker_instance', 'tracker_generation', 'target_status', 'task_id', 'source_commit', 'run_id')


def validate_config(cfg, horizon):
    if cfg.nonprogress_tangent_mode != 'off' and (cfg.closure_intent_mode != 'off' or cfg.n35_runtime_binding is not None):
        raise ValueError('N36 requires N35 disabled')
    if cfg.nonprogress_tangent_mode == 'off':
        if cfg.n36_runtime_binding is not None:
            raise ValueError('N36 binding with memory disabled')
        return
    if cfg.nonprogress_tangent_mode != MODE or cfg.observed_jaw_approach_mode != N34_MODE or horizon != 8:
        raise ValueError('N36 requires explicit mode and N34 fallback')
    if cfg.n36_runtime_binding != cfg.n34_runtime_binding or cfg.n36_runtime_binding is None:
        raise ValueError('N36 explicit shared task/source/run binding required')


def physical_eef(packet):
    value = None if packet is None else packet.get('observed_eef')
    if value is None:
        return None
    if not torch.is_tensor(value) or value.shape != (3,) or not value.is_floating_point():
        raise ValueError('N36 malformed EEF measurement')
    values = value.detach().cpu().double().tolist()
    return values if all(math.isfinite(x) for x in values) else None


def predicted_translation(decoded):
    # Explicit binary64 j-order; neither torch reduction nor fsum is equivalent.
    if decoded.shape != (1, 8, 7) or decoded.dtype != torch.float32:
        raise ValueError('N36 requires decoded fp32 full8')
    values = decoded.detach().cpu().double().tolist()[0]
    if not all(math.isfinite(x) for row in values for x in row):
        return None
    sums = [0., 0., 0.]
    for row in values:
        for k in range(3):
            sums[k] = sums[k] + row[k]
    p = [0.01 * v for v in sums]
    return p if all(math.isfinite(x) for x in sums + p) else None


def nonprogress(p, prior_eef, current_eef):
    if p is None or prior_eef is None or current_eef is None:
        return False, None, None, 'physical_data_unavailable'
    if not all(math.isfinite(x) for x in p + prior_eef + current_eef):
        return False, None, None, 'physical_data_unavailable'
    length = math.hypot(*p)
    if not math.isfinite(length) or length == 0.:
        return False, None, None, 'zero_or_nonfinite_prediction'
    d = [current_eef[k] - prior_eef[k] for k in range(3)]
    dot = 0.
    for k in range(3):
        product = p[k] * d[k]
        dot = dot + product
        if not math.isfinite(product) or not math.isfinite(dot):
            return False, d, None, 'nonfinite_displacement_or_dot'
    if not all(math.isfinite(x) for x in d):
        return False, d, None, 'nonfinite_displacement_or_dot'
    return dot <= 0., d, dot, 'nonprogress_consumed' if dot <= 0. else 'positive_progress'


def recognized(identity):
    return (all(k in identity and identity[k] is not None for k in CONTINUITY)
        and identity['target_status'] in ('tracked', 'static_background')
        and isinstance(identity['provider'], dict) and bool(identity['provider'])
        and all(type(identity.get(k)) is int and identity[k] >= 0 for k in
            ('episode', 'stage', 'target_index', 'tracker_instance', 'tracker_generation', 'task_id', 'step'))
        and isinstance(identity.get('decision_id'), str) and bool(identity['decision_id'])
        and isinstance(identity['source_commit'], str) and len(identity['source_commit']) == 40
        and all(c in '0123456789abcdef' for c in identity['source_commit'])
        and isinstance(identity['run_id'], str) and bool(identity['run_id']))


def clear_on_error(method):
    from functools import wraps
    @wraps(method)
    def wrapped(self,*args,**kwargs):
        try:return method(self,*args,**kwargs)
        except BaseException:
            self.reset('exception')
            raise
    return wrapped


class NonprogressMemory:
    def __init__(self):
        self.previous = None
        self.identity = None
        self.latch = False
        self.boundary_open = False
        self.evidence = None

    def record(self, event, **values):
        if self.evidence is not None:
            self.evidence.record('n36_' + event, **values)

    def reset(self, reason):
        self.previous = None
        self.identity = None
        self.latch = False
        self.boundary_open = False
        self.record('memory_reset', reason=reason)

    @clear_on_error
    def enter(self, identity, packet, *, guided, evidence=None):
        self.evidence = evidence
        if self.boundary_open:
            self.reset('exception')
            raise RuntimeError('N36 nested boundary')
        prior, self.previous = self.previous, None  # consume exactly once
        self.identity = copy.deepcopy(identity)
        self.boundary_open = True
        self.latch = False
        reason = 'no_prior_chunk'
        eef = physical_eef(packet)
        displacement = dot = None
        if not guided:
            reason = 'unguided'
        elif prior is not None:
            if not recognized(identity) or not recognized(prior['identity']) or any(identity[k] != prior['identity'][k] for k in CONTINUITY):
                reason = 'identity_or_tracking_change'
            elif identity['step'] != prior['identity']['step'] + 8 or identity['decision_id'] == prior['identity']['decision_id']:
                reason = 'not_immediate_prior_chunk'
            elif prior['origin'] != 'observed_open_approach':
                reason = 'non_direct_open_origin'
            elif prior['ambiguous']:
                reason = 'ambiguous_equal_content_origins'
            elif prior['completed'] is not True or prior['committed'] is not True or prior['acknowledged'] != 8:
                reason = 'incomplete_execution'
            elif prior['open_translation'] is not True:
                reason = 'non_open_translation_commands'
            else:
                self.latch, displacement, dot, reason = nonprogress(prior['p'], prior['eef'], eef)
        self.record('boundary_entry', identity=self.identity, guided=guided,
                    prior=prior, eef=eef, displacement=displacement, dot=dot, eligible=self.latch, reason=reason)
        return self.latch

    @clear_on_error
    def select(self, decision, entry, selected):
        if not self.boundary_open or self.identity != decision.identity:
            raise RuntimeError('N36 selection outside boundary')
        occurrence = entry.occurrence_id
        if type(occurrence) is not int or not 0 <= occurrence < len(decision.entries):
            raise ValueError('N36 selected archive occurrence missing')
        source = decision.entries[occurrence]
        if (source['occurrence'] != occurrence or source['iteration'] != entry.source_iter
                or not same(source['plan'], entry.action) or not same(selected[0], entry.action)):
            raise ValueError('N36 selected occurrence/content mismatch')
        origin = decision.origins[occurrence]
        aliases = [x['occurrence'] for x in decision.entries if same(x['plan'], entry.action)]
        # The transported winner resolves equal-content aliases. Never infer
        # origin from any alias: an ordinary/memory occurrence stays that origin
        # even when its bytes equal a direct N34 proposal. Missing/merged
        # occurrence transport was rejected above as a mandatory audit failure.
        ambiguous = False
        self.previous = dict(identity=copy.deepcopy(self.identity), occurrence=occurrence,
            origin=origin, ambiguous=ambiguous, aliases=aliases,
            native=selected.detach().cpu().clone(), native_identity=native_id(selected),
            decoded=None, decoded_identity=None, completed=False, open_translation=None, p=None,
            committed=False, acknowledged=0, eef=physical_eef(decision.packet))
        self.record('selected_occurrence', **self.previous)

    def finish(self):
        if not self.boundary_open:
            raise RuntimeError('N36 boundary already expired')
        self.record('boundary_expiry', identity=self.identity, eligible=self.latch,
                    selected=self.previous is not None)
        self.latch = False
        self.boundary_open = False

    @clear_on_error
    def bind_decode(self, native, decoded):
        p = self.previous
        if p is None:
            return
        if p['decoded'] is not None:
            raise ValueError('N36 duplicate decoder')
        # Policy returns its native selection as float32 before postprocessing.
        if not same(native.detach().cpu(), p['native'].float()):
            self.reset('decode_failure'); raise ValueError('N36 decoder native identity')
        expected = decode_rdt_libero_action_chunk(p['native'], 8)
        if not same(decoded.detach().cpu(), expected):
            self.reset('decode_failure'); raise ValueError('N36 actual decoder differs')
        p['decoded'] = decoded.detach().cpu().clone()
        p['decoded_identity'] = native_id(p['decoded'])
        self.record('decode_binding', occurrence=p['occurrence'], native_identity=p['native_identity'],
                    decoded=p['decoded'], decoded_identity=native_id(p['decoded']))

    @clear_on_error
    def commit(self, actions, horizon, step):
        p = self.previous
        if p is None:
            return
        if horizon != 8:
            self.reset('incomplete_execution'); raise ValueError('N36 requires full8 commit')
        if p['committed'] or p['decoded'] is None or step != p['identity']['step'] or not same(actions.detach().cpu(), p['decoded']):
            self.reset('commit_failure'); raise ValueError('N36 commit/decode identity')
        p['committed'] = True
        self.record('execution_commit', occurrence=p['occurrence'], step=step, horizon=horizon,
                    decoded_identity=native_id(p['decoded']))

    @clear_on_error
    def acknowledge(self, *, action, step, index, terminated, truncated):
        p = self.previous
        if p is None:
            return
        j = p['acknowledged']
        if (p['committed'] is not True or j >= 8 or index != j+1 or step != p['identity']['step']+j
                or not same(torch.as_tensor(action).detach().cpu(), p['decoded'][0,j])):
            self.reset('acknowledgement_failure'); raise ValueError('N36 step-return/decode identity')
        # Terminal flags are validated by the generic recorder as well.
        end = bool(torch.as_tensor(terminated).item()) or bool(torch.as_tensor(truncated).item())
        p['acknowledged'] += 1
        self.record('step_acknowledged', occurrence=p['occurrence'], index=index, step=step,
                    action=p['decoded'][0,j], native_identity=p['native_identity'], ended=end)
        if end:
            self.reset('terminal')
        elif p['acknowledged'] == 8:
            p['completed'] = True
            p['open_translation'] = bool((p['decoded'][0,:,6] == -1).all() and (p['decoded'][0,:,3:6] == 0).all())
            p['p'] = predicted_translation(p['decoded'])
            self.record('execution_complete', occurrence=p['occurrence'], origin=p['origin'],
                        open_translation=p['open_translation'], p=p['p'], ambiguous=p['ambiguous'],
                        native_identity=p['native_identity'], decoded_identity=p['decoded_identity'])
            # Completed memory is an intent witness, never a retained trajectory.
            # Full tensors remain only in the passive evidence stream.
            p['native'] = None
            p['decoded'] = None


@torch.no_grad()
def propose(plan, *, target, observed_eef, hand_quaternion_xyzw, gripper_qpos, target_recognized):
    _native(plan, (64, 128), 'plan')
    if type(target_recognized) is not bool:
        raise ValueError('N36 explicit recognition required')
    if not target_recognized:
        return CaptureDwellProposal(None, None, 'unrecognized_target'), None
    vectors = []
    for value, n, name in ((target, 3, 'target'), (observed_eef, 3, 'EEF'),
            (hand_quaternion_xyzw, 4, 'quaternion'), (gripper_qpos, 2, 'jaw')):
        if torch.is_tensor(value) and not bool(torch.isfinite(value).all()):
            return CaptureDwellProposal(None, None, 'nonfinite_observation'), None
        vectors.append(_geometry_vector(value, n, name))
    point, eef, quat, jaw = vectors
    if any(v is None for v in vectors):
        return CaptureDwellProposal(None, None, 'observation_unavailable'), None
    norm = math.hypot(*quat)
    if not math.isfinite(norm) or norm == 0:
        return CaptureDwellProposal(None, None, 'invalid_quaternion'), None
    # Same binary64 normalized xyzw convention and operation order as N31.
    try:
        norm = math.sqrt(math.fsum(v*v for v in quat))
    except (OverflowError, ValueError):
        return CaptureDwellProposal(None, None, 'invalid_quaternion'), None
    if not math.isfinite(norm) or norm == 0:
        return CaptureDwellProposal(None, None, 'invalid_quaternion'), None
    x, y, z, w = (v/norm for v in quat)
    r = ((1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)),
         (2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)),
         (2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)))
    lower, upper = jaw[1]+.0005, jaw[0]-.0005
    if lower > upper:
        return CaptureDwellProposal(None, None, 'empty_inner_gap'), None
    delta = [point[k]-eef[k] for k in range(3)]
    if not all(math.isfinite(v) for v in delta):
        return CaptureDwellProposal(None, None, 'nonfinite_observation'), None
    local = [math.fsum(r[k][axis]*delta[k] for k in range(3)) for axis in range(3)]
    inside = -.008 <= local[0] <= .008 and lower <= local[1] <= upper and -.0116 <= local[2] <= .0044
    path = None
    commands = [[0., 0., 0., 0., 0., 0., 1.] for _ in range(8)]
    if not inside:
        center = (0., (lower+upper)/2, -.0036)
        world = [math.fsum(r[k][axis]*center[axis] for axis in range(3)) for k in range(3)]
        error = [delta[k] - world[k] for k in range(3)]
        length = math.hypot(*error)
        if not all(math.isfinite(v) for v in error) or not math.isfinite(length) or length == 0.:
            return CaptureDwellProposal(None, None, 'invalid_tangent_error'), None
        axis = min(range(3), key=lambda k: (abs(error[k]), k))
        unit = [float(k == axis) for k in range(3)]
        cross = [error[1]*unit[2]-error[2]*unit[1], error[2]*unit[0]-error[0]*unit[2], error[0]*unit[1]-error[1]*unit[0]]
        length_cross = math.hypot(*cross)
        if not math.isfinite(length_cross) or length_cross == 0.:
            return CaptureDwellProposal(None, None, 'invalid_tangent_cross'), None
        tangent = [v/length_cross for v in cross]
        a = [max(-1., min(1., v/(8*.01))) for v in error]
        b = [v*math.hypot(*a) for v in tangent]
        halves = [[a[k]+b[k] for k in range(3)], [a[k]-b[k] for k in range(3)]]
        clipped = [[max(-1., min(1., v)) for v in half] for half in halves]
        commands = [clipped[j//4] + [0., 0., 0., -1.] for j in range(8)]
        path = dict(error=error, axis=axis, tangent=tangent, a=a, b=b, preclip=halves, clipped=clipped)
    # A single binary64 -> native conversion; preserve every untouched byte.
    command = torch.tensor(commands, dtype=plan.dtype, device=plan.device)
    candidate = encode_libero_prefix(plan, command)
    if path is not None:
        decoded = decode_rdt_libero_action_chunk(candidate[None], 8)
        translation = predicted_translation(decoded)
        path.update(native_commands=command.detach().cpu().clone(), decoded_translation=translation,
            proxy_endpoint=[eef[k]+translation[k] for k in range(3)])
    reason = 'observed_close_dwell' if inside else 'nonprogress_tangent'
    if same(candidate, plan):
        return CaptureDwellProposal(None, 0 if inside else None, 'no_native_change'), path
    return CaptureDwellProposal(candidate, 0 if inside else None, reason), path


class _Recorder:
    def __init__(self, recorder):
        self.recorder = recorder
        self.scoring_batch_id = recorder.scoring_batch_id
    def record(self, event, **values):
        self.recorder.record(event.replace('n34_', 'n36_', 1), **values)


@dataclass(frozen=True)
class BoundaryLatch:
    eligible: bool


class NonprogressDecision(ObservedJawDecision):
    event_prefix = 'n36'

    @property
    def memory_eligible(self):
        return self._boundary_latch.eligible

    def __init__(self, *args, memory, evidence=None, **kwargs):
        super().__init__(*args, **kwargs)
        import hashlib
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        self.source_hashes = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in SOURCE_FILES}
        self.identity.update(self.binding)
        self.identity['decision_id'] = evidence.decision_id if evidence is not None else f"e{self.identity['episode']}:s{self.identity['step']}"
        self.memory = memory
        self.origins = []
        if evidence is not None:
            evidence.record('n36_native_runtime', device=str(self.mask.device), dtype=str(self.mask.dtype),
                torch_version=str(torch.__version__), cuda_version=torch.version.cuda, torch_build=torch.__config__.show())
        self.memory.enter(self.identity, self.packet, guided=True, evidence=evidence)
        self._boundary_latch = BoundaryLatch(self.memory.latch)

    def record_score(self, samples, projection, rewards, costs, evidence, **kwargs):
        canonical = self.canonical()
        super().record_score(samples, projection, rewards, costs,
                             None if evidence is None else _Recorder(evidence), **kwargs)
        if canonical:
            origin = self.opportunities[-1]['reason'] if self.opportunities and self.opportunities[-1]['changed'] else 'ordinary'
            self.origins.extend(['ordinary']*15 + [origin] if self.batches > 1 else ['ordinary']*16)

    def prepare(self, archive, iteration, providers, keypoints, evidence):
        if self.closed or not self.memory.boundary_open or self.memory.identity != self.identity:
            raise RuntimeError('N36 expired decision latch')
        super().prepare(archive, iteration, providers, keypoints, evidence)
        cell, best = archive.select_global_best()
        if type(best.occurrence_id) is not int or best.occurrence_id not in self.pending['matching_occurrences']:
            raise ValueError('N36 template direct occurrence missing')
        self.pending['template_occurrence'] = best.occurrence_id
        self.pending['memory_eligible'] = self.memory_eligible
        self.pending['path'] = None
        if self.memory_eligible and not self.reason:
            result, path = propose(best.action, target=self.target, observed_eef=self.packet['observed_eef'],
                hand_quaternion_xyzw=self.packet['hand_quaternion_xyzw'], gripper_qpos=self.packet['gripper_qpos'], target_recognized=True)
            self.pending.update(candidate=result.candidate, arrival_index=result.arrival_index, reason=result.reason, path=path)
        candidate = self.pending['candidate']
        template = best.action
        self.pending['native_delta_count'] = 0 if candidate is None else int((candidate.contiguous().view(torch.uint8).reshape(-1,candidate.element_size()) !=
            template.contiguous().view(torch.uint8).reshape(-1,template.element_size())).any(dim=1).sum())
        self.pending['decoded_delta_count'] = 0 if candidate is None else int((
            decode_rdt_libero_action_chunk(candidate[None],8) != decode_rdt_libero_action_chunk(template[None],8)).sum())

    def apply(self, population, evidence):
        if self.closed or not self.memory.boundary_open:
            raise RuntimeError("N36 expired proposal")
        if self.pending is not None:
            self.pending["ordinary_population"] = population.detach().clone() if evidence is not None else None
        return super().apply(population, None if evidence is None else _Recorder(evidence))

    def close(self):
        native_deltas = [x["native_delta_count"] for x in self.opportunities]
        decoded_deltas = [x["decoded_delta_count"] for x in self.opportunities]
        result = super().close()
        result.update(native_delta_counts=native_deltas, decoded_delta_counts=decoded_deltas,
                      memory_eligible=self.memory_eligible)
        self.memory.finish()
        result.update(schema='n36-nonprogress-tangent-scalar-v1', mode=MODE)
        result['overhead_excludes'] += ['N36_source_hashing', 'N36_lifecycle_and_origin_observer']
        return result


def reset_on_failure(method):
    """Selection/decode exceptions must not leave a reusable pending token."""
    from functools import wraps
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except BaseException:
            memory = getattr(self, '_nonprogress_tangent', None)
            if memory is not None:
                memory.reset('exception')
            raise
    return wrapped
