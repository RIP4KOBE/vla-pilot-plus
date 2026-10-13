"""Lossless presentation decoding; field/schema validation is separate."""


def unwrap(text):
    if not isinstance(text, str):
        raise TypeError('observation text must be a string')
    text = text.strip()
    lines = text.splitlines()
    if (len(lines) >= 3 and lines[0].strip().lower() in {'```json', '```'}
            and lines[-1].strip() == '```'):
        return '\n'.join(lines[1:-1]).strip(), 'single_json_fence'
    return text, 'bare_json'
