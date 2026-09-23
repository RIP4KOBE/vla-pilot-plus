"""Unlaunched first-render diagnostic primitive. No environment/GPU imports.

Requires an already-installed, idle NativeRenderLifetime owner whose original
native resources were retired. The caller owns all admission, native guards,
baseline equality checks and raw-array serialization. A mismatching first frame
is retained as a failed identity gate; capture must not silently discard it.
"""


def capture_wrist_pair(owner, capture, state_snapshot):
    """One native creation, two original same-camera renders, one retirement.

    capture(ordinal, result, before_state, after_state) must save both outputs.
    Native/nonfinite/capture exceptions stop immediately, without a retry.
    Cleanup failure cannot turn the operation into success or mask its original
    exception. This function neither reconstructs a simulator nor advances it.
    """
    owner._enter()
    context, sim = owner._context(), owner._sim()
    error = None
    records = []
    try:
        if context is None or sim is None or sim._render_context_offscreen is not context:
            raise RuntimeError('managed context identity differs')
        if any(name in vars(context) for name in ('con', 'gl_ctx')):
            raise RuntimeError('pair requires retired native resources')
        owner._ensure_native(context)
        for ordinal in (1, 2):
            before = state_snapshot(sim)
            result = owner._original_render(sim, camera_name='robot0_eye_in_hand',
                width=128, height=128, depth=True)
            after = state_snapshot(sim)
            records.append(capture(ordinal, result, before, after))
        return records
    except BaseException as exc:
        error = exc
        owner.failed = True
        raise
    finally:
        try:
            okay = context is not None and owner._retire_native(context)
            if not okay:
                owner.failed = True
                if error is None:
                    raise RuntimeError('paired native retirement not verified')
        except BaseException:
            owner.failed = True
            if error is None:
                raise
        finally:
            owner._busy = False
            owner._call_lock.release()
