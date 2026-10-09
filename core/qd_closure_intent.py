"""N35 one-boundary executed-closure intent. No replay or forced selection.

Occurrence IDs are transported by QDArchive, never recovered from hashes.
The optional observer is passive; missing physical trigger fields mean ineligible,
whereas contradictory occurrence/decode/ack records raise and reset the state.
"""
from dataclasses import dataclass
import copy
import torch
from core.qd_capture_dwell import native_id
from core.qd_capture_dwell_proposal import _same_native_bytes as same
from core.qd_observed_jaw_approach import ObservedJawDecision, MODE as N34_MODE, SOURCE_FILES as N34_SOURCES
from core.rdt_libero_action_converter import decode_rdt_libero_action_chunk

MODE = 'executed_closure_intent_v1'
SOURCE_FILES = N34_SOURCES + ('core/qd_closure_intent.py',)
CONTINUITY = ('episode', 'stage', 'provider', 'target_index', 'tracker_instance', 'tracker_generation', 'target_status')


def validate_config(cfg, horizon):
    if cfg.closure_intent_mode == 'off':
        if cfg.n35_runtime_binding is not None:
            raise ValueError('N35 binding with memory disabled')
        return
    if cfg.closure_intent_mode != MODE or cfg.observed_jaw_approach_mode != N34_MODE:
        raise ValueError('N35 requires explicit mode and N34 fallback')
    if cfg.n35_runtime_binding != cfg.n34_runtime_binding or cfg.n35_runtime_binding is None:
        raise ValueError('N35 explicit shared task/source/run binding required')


def jaw_separation(packet):
    jaw = None if packet is None else packet.get('gripper_qpos')
    if jaw is None:
        return None
    if not torch.is_tensor(jaw) or jaw.shape != (2,) or not jaw.is_floating_point():
        raise ValueError('N35 malformed jaw measurement')
    values = jaw.detach().cpu().double()
    if not bool(torch.isfinite(values).all()):
        return None
    separation = float(values[0]) - float(values[1])
    return separation if __import__('math').isfinite(separation) else None


class ClosureIntentMemory:
    def __init__(self):
        self.previous = None
        self.identity = None
        self.latch = False
        self.boundary_open = False
        self.evidence = None

    def record(self, event, **values):
        if self.evidence is not None:
            self.evidence.record('n35_' + event, **values)

    def reset(self, reason):
        self.previous = None
        self.identity = None
        self.latch = False
        self.boundary_open = False
        self.record('memory_reset', reason=reason)

    def enter(self, identity, packet, *, guided, evidence=None):
        self.evidence = evidence
        if self.boundary_open:
            self.reset('exception')
            raise RuntimeError('N35 nested boundary')
        prior, self.previous = self.previous, None  # consume exactly once
        self.identity = copy.deepcopy(identity)
        self.boundary_open = True
        self.latch = False
        reason = 'no_prior_chunk'
        separation = jaw_separation(packet)
        if not guided:
            reason = 'unguided'
        elif prior is not None:
            if any(k not in identity or k not in prior['identity'] or identity[k] != prior['identity'][k] for k in CONTINUITY):
                reason = 'identity_or_tracking_change'
            elif identity['step'] != prior['identity']['step'] + 8:
                reason = 'not_immediate_prior_chunk'
            elif prior['origin'] != 'observed_close_dwell':
                reason = 'non_direct_close_origin'
            elif prior['ambiguous']:
                reason = 'ambiguous_equal_content_origins'
            elif prior['completed'] is not True or prior['committed'] is not True or prior['acknowledged'] != 8:
                reason = 'incomplete_execution'
            elif prior['positive'] is not True:
                reason = 'nonpositive_executed_commands'
            elif separation is None or prior['jaw'] is None:
                reason = 'jaw_unavailable'
            elif not separation < prior['jaw']:
                reason = 'jaw_not_strictly_decreasing'
            else:
                self.latch = True
                reason = 'executed_close_consumed'
        self.record('boundary_entry', identity=self.identity, guided=guided,
                    prior=prior, jaw=separation, eligible=self.latch, reason=reason)
        return self.latch

    def select(self, decision, entry, selected):
        if not self.boundary_open or self.identity != decision.identity:
            raise RuntimeError('N35 selection outside boundary')
        occurrence = entry.occurrence_id
        if type(occurrence) is not int or not 0 <= occurrence < len(decision.entries):
            raise ValueError('N35 selected archive occurrence missing')
        source = decision.entries[occurrence]
        if (source['occurrence'] != occurrence or source['iteration'] != entry.source_iter
                or not same(source['plan'], entry.action) or not same(selected[0], entry.action)):
            raise ValueError('N35 selected occurrence/content mismatch')
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
            decoded=None, decoded_identity=None, completed=False, positive=None,
            committed=False, acknowledged=0, jaw=jaw_separation(decision.packet))
        self.record('selected_occurrence', **self.previous)

    def finish(self):
        if not self.boundary_open:
            raise RuntimeError('N35 boundary already expired')
        self.record('boundary_expiry', identity=self.identity, eligible=self.latch,
                    selected=self.previous is not None)
        self.latch = False
        self.boundary_open = False

    def bind_decode(self, native, decoded):
        p = self.previous
        if p is None:
            return
        # Policy returns its native selection as float32 before postprocessing.
        if not same(native.detach().cpu(), p['native'].float()):
            self.reset('decode_failure'); raise ValueError('N35 decoder native identity')
        expected = decode_rdt_libero_action_chunk(p['native'], 8)
        if not same(decoded.detach().cpu(), expected):
            self.reset('decode_failure'); raise ValueError('N35 actual decoder differs')
        p['decoded'] = decoded.detach().cpu().clone()
        p['decoded_identity'] = native_id(p['decoded'])
        self.record('decode_binding', occurrence=p['occurrence'], native_identity=p['native_identity'],
                    decoded=p['decoded'], decoded_identity=native_id(p['decoded']))

    def commit(self, actions, horizon, step):
        p = self.previous
        if p is None:
            return
        if horizon != 8:
            self.reset('incomplete_execution'); return
        if p['committed'] or p['decoded'] is None or step != p['identity']['step'] or not same(actions.detach().cpu(), p['decoded']):
            self.reset('commit_failure'); raise ValueError('N35 commit/decode identity')
        p['committed'] = True
        self.record('execution_commit', occurrence=p['occurrence'], step=step, horizon=horizon,
                    decoded_identity=native_id(p['decoded']))

    def acknowledge(self, *, action, step, index, terminated, truncated):
        p = self.previous
        if p is None:
            return
        j = p['acknowledged']
        if (p['committed'] is not True or j >= 8 or index != j+1 or step != p['identity']['step']+j
                or not same(torch.as_tensor(action).detach().cpu(), p['decoded'][0,j])):
            self.reset('acknowledgement_failure'); raise ValueError('N35 step-return/decode identity')
        # Terminal flags are validated by the generic recorder as well.
        end = bool(torch.as_tensor(terminated).item()) or bool(torch.as_tensor(truncated).item())
        p['acknowledged'] += 1
        self.record('step_acknowledged', occurrence=p['occurrence'], index=index, step=step,
                    action=p['decoded'][0,j], native_identity=p['native_identity'], ended=end)
        if end:
            self.reset('terminal')
        elif p['acknowledged'] == 8:
            p['completed'] = True
            p['positive'] = bool((p['decoded'][0,:,6] > 0).all())
            self.record('execution_complete', occurrence=p['occurrence'], origin=p['origin'],
                        positive=p['positive'], ambiguous=p['ambiguous'],
                        native_identity=p['native_identity'], decoded_identity=p['decoded_identity'])
            # Completed memory is an intent witness, never a retained trajectory.
            # Full tensors remain only in the passive evidence stream.
            p['native'] = None
            p['decoded'] = None


class _Recorder:
    def __init__(self, recorder):
        self.recorder = recorder
        self.scoring_batch_id = recorder.scoring_batch_id
    def record(self, event, **values):
        self.recorder.record(event.replace('n34_', 'n35_', 1), **values)


@dataclass(frozen=True)
class BoundaryLatch:
    eligible: bool


class ClosureIntentDecision(ObservedJawDecision):
    event_prefix = 'n35'

    @property
    def memory_eligible(self):
        return self._boundary_latch.eligible

    def __init__(self, *args, memory, evidence=None, **kwargs):
        super().__init__(*args, **kwargs)
        import hashlib
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        self.source_hashes = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in SOURCE_FILES}
        self.memory = memory
        self.origins = []
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
        super().prepare(archive, iteration, providers, keypoints, evidence)
        cell, best = archive.select_global_best()
        if type(best.occurrence_id) is not int or best.occurrence_id not in self.pending['matching_occurrences']:
            raise ValueError('N35 template direct occurrence missing')
        self.pending['template_occurrence'] = best.occurrence_id
        self.pending['memory_eligible'] = self.memory_eligible
        if self.memory_eligible:
            candidate = best.action.detach().clone()
            candidate[:8,10] = 1
            self.pending.update(candidate=candidate, arrival_index=None, reason='closure_intent_memory')
        candidate = self.pending['candidate']
        template = best.action
        self.pending['native_delta_count'] = 0 if candidate is None else int((candidate.contiguous().view(torch.uint8).reshape(-1,candidate.element_size()) !=
            template.contiguous().view(torch.uint8).reshape(-1,template.element_size())).any(dim=1).sum())
        self.pending['decoded_delta_count'] = 0 if candidate is None else int((
            decode_rdt_libero_action_chunk(candidate[None],8) != decode_rdt_libero_action_chunk(template[None],8)).sum())

    def apply(self, population, evidence):
        return super().apply(population, None if evidence is None else _Recorder(evidence))

    def close(self):
        native_deltas = [x["native_delta_count"] for x in self.opportunities]
        decoded_deltas = [x["decoded_delta_count"] for x in self.opportunities]
        result = super().close()
        result.update(native_delta_counts=native_deltas, decoded_delta_counts=decoded_deltas,
                      memory_eligible=self.memory_eligible)
        self.memory.finish()
        result.update(schema='n35-closure-intent-scalar-v1', mode=MODE)
        result['overhead_excludes'] += ['N35_source_hashing', 'N35_lifecycle_and_origin_observer']
        return result


def reset_on_failure(method):
    """Selection/decode exceptions must not leave a reusable pending token."""
    from functools import wraps
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except BaseException:
            memory = getattr(self, '_closure_intent', None)
            if memory is not None:
                memory.reset('exception')
            raise
    return wrapped
