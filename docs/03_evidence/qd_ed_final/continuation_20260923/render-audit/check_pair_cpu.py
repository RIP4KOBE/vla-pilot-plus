"""Three CPU-only checks of the diagnostic call primitive, no graphics imports."""
import threading
from types import SimpleNamespace
from paired_native_first_frame import capture_wrist_pair


class Owner:
    def __init__(self, error=None, cleanup=True):
        self.context = SimpleNamespace()
        self.sim = SimpleNamespace(_render_context_offscreen=self.context)
        self._call_lock = threading.Lock()
        self.failed = False
        self.error, self.cleanup = error, cleanup
        self.calls = []

    def _context(self): return self.context
    def _sim(self): return self.sim
    def _enter(self):
        assert self._call_lock.acquire(blocking=False)
        self._busy = True
        self.calls.append('enter')
    def _ensure_native(self, context):
        assert context is self.context
        self.calls.append('create')
        context.con, context.gl_ctx = object(), object()
    def _original_render(self, sim, **request):
        assert sim is self.sim
        assert request == dict(camera_name='robot0_eye_in_hand', width=128, height=128, depth=True)
        self.calls.append('render')
        if self.error is not None: raise self.error
        return object()
    def _retire_native(self, context):
        self.calls.append('retire')
        context.__dict__.clear()
        return self.cleanup


def run():
    owner = Owner()
    captured = []
    def capture(ordinal, result, before, after):
        assert result is not None and before == after == 'same CPU physical/derived state'
        captured.append(ordinal)
        return {'ordinal': ordinal, 'canonical_matches': ordinal == 2}
    records = capture_wrist_pair(owner, capture, lambda sim: 'same CPU physical/derived state')
    assert owner.calls == ['enter', 'create', 'render', 'render', 'retire']
    assert captured == [1, 2] and records[0]['canonical_matches'] is False
    assert not owner.failed and not owner._busy and not owner._call_lock.locked()
    marker = ValueError('original render error')
    owner = Owner(error=marker, cleanup=False)
    try: capture_wrist_pair(owner, capture, lambda sim: 'state')
    except ValueError as exc: assert exc is marker
    else: raise AssertionError('original exception lost')
    assert owner.calls == ['enter', 'create', 'render', 'retire']
    assert owner.failed and not owner._call_lock.locked()
    owner = Owner(cleanup=False)
    try: capture_wrist_pair(owner, lambda *args: None, lambda sim: 'state')
    except RuntimeError as exc: assert 'retirement' in str(exc)
    else: raise AssertionError('cleanup failure accepted')
    assert owner.failed and not owner._call_lock.locked()
    print('3 CPU checks passed; no GPU/backend/model imports')


if __name__ == '__main__': run()
