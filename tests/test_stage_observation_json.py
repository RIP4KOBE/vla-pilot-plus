import json
import pytest
from core.stage_evidence import parse_observation
from core.stage_response_validation import request_validated, ObservationValidationError


OBS=dict(target_visibility='unknown',target_location='unknown',grasp='unknown',support='unknown',evidence='Hidden by the basket.')
TEXT=json.dumps(OBS)


@pytest.mark.parametrize('text',[TEXT,'```json\n'+TEXT+'\n```','```\n'+TEXT+'\n```',
    ' \r\n```JSON\r\n'+TEXT+'\r\n``` \r\n'])
def test_bare_and_single_complete_json_fence_have_identical_semantics(text):
    assert parse_observation(text)==OBS


@pytest.mark.parametrize('text',[
    'The answer is:\n```json\n'+TEXT+'\n```',
    '```json\n'+TEXT+'\n```\nExtra explanation.',
    '```json\n'+TEXT, '```json\n'+TEXT[:-1]+'\n```',
    '```python\n'+TEXT+'\n```',
    '```json\n'+TEXT+'\n```\n```json\n'+TEXT+'\n```',
    '```json\n'+TEXT+'\n'+TEXT+'\n```',
    '```json\n{"grasp":"held","grasp":"not_held"}\n```',
    '```json\n{"stage":2,"use_guidance":false}\n```',
])
def test_prose_truncation_ambiguity_and_wrong_schema_still_fail(text):
    with pytest.raises((ValueError,TypeError)):
        parse_observation(text)


def test_first_fenced_unknown_answer_is_accepted_without_semantic_retry():
    class Observer:
        cursor=0
        _last_completion_metadata={'finish_reason':'stop'}
        def _request_stage_response(self,content):
            self.cursor+=1
            assert self.cursor==1
            return '```json\n'+TEXT+'\n```'
    raw,obs,attempts=request_validated(Observer(),[{'type':'text','text':'fixed'}],2)
    assert raw.startswith('```json') and obs==OBS and len(attempts)==1
    assert attempts[0]['presentation']=='single_json_fence'


def test_length_finish_reason_rejects_even_a_complete_looking_fence():
    class Observer:
        cursor=0
        _last_completion_metadata={'finish_reason':'length'}
        def _request_stage_response(self,content):
            self.cursor+=1
            return '```json\n'+TEXT+'\n```'
    with pytest.raises(ObservationValidationError) as error:
        request_validated(Observer(),[],2)
    assert len(error.value.attempts)==2 and not any(x['valid'] for x in error.value.attempts)
