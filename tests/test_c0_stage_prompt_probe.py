"""The optional Stage prompt changes guidance semantics only."""

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from c0_stage_prompt_probe import NEW_TEMPLATE, OLD_TEMPLATE, REPLACEMENTS


def test_guidance_persistence_prompt_is_exactly_the_declared_edit():
    text = OLD_TEMPLATE.read_text()
    for old, new in REPLACEMENTS:
        assert text.count(old) == 1
        text = text.replace(old, new, 1)
    assert text == NEW_TEMPLATE.read_text()
