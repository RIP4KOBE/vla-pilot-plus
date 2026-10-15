"""Per-episode online object appearance memory, not stored Stage replies."""
import hashlib


def identify(observer, *, instruction, initial_image, mapping):
    from core.gemini_grounder import _image_to_base64
    if initial_image is None:
        raise ValueError('identity memory requires the actual initial reference image')
    context = getattr(observer, 'context', {})
    image_hash = hashlib.sha256(initial_image.tobytes()).hexdigest()
    key = (context.get('episode_id'), context.get('task_id'), instruction, image_hash)
    if getattr(observer, '_identity_memory_key', None) == key:
        return observer._identity_memory, False
    labels = '\n'.join(f'{k}: {v}' for k, v in mapping.items())
    prompt = ('Identify only the instructed target object. Task: '+instruction+'\n'
              'The initial image is annotated with these object keypoint labels:\n'+labels+'\n'
              'Describe the exact target by visible shape, colors, label and size so it can be '
              'recognized in another camera frame. Distinguish it from neighboring distractors. '
              'Do not describe robot actions or infer any current grasp or task success. '
              'Do not give commands or control decisions. Use under 100 words.')
    description = observer._request_stage_response([dict(type='text',text=prompt),
        dict(type='image_url',image_url=dict(url='data:image/png;base64,'+_image_to_base64(initial_image)))])
    if (observer._last_completion_metadata or {}).get('finish_reason') == 'length':
        raise ValueError('truncated identity description')
    if not isinstance(description,str) or not description.strip() or len(description)>2400:
        raise ValueError('invalid identity description')
    observer._identity_memory_key = key
    observer._identity_memory = description
    return description, True
