from types import SimpleNamespace
import json
import pytest
from core.stage.contract import request_validated, ObservationValidationError


def observer(replies,finish='stop'):
    requests=[];iterator=iter(replies)
    def request(content):
        requests.append(content)
        return next(iterator)
    return SimpleNamespace(_request_stage_response=request,_last_completion_metadata={'finish_reason':finish},
                           requests=requests)


UNKNOWN=json.dumps(dict(target_visibility='unknown',target_location='unknown',grasp='unknown',
                        support='unknown',evidence='Target is not visible.'))


def test_truncated_stop_response_is_rejected_then_exact_same_payload_is_requested():
    rec=observer(['{"target_visibility":"unknown",',UNKNOWN])
    content=[{'type':'text','text':'same original prompt and frame'}]
    raw,obs,attempts=request_validated(rec,content,2)
    assert obs['grasp']=='unknown' and len(attempts)==2
    assert rec.requests[0] is rec.requests[1] is content
    assert not attempts[0]['valid'] and attempts[0]['raw_response'].endswith(',')


def test_valid_unknown_or_negative_answer_is_never_retried():
    rec=observer([UNKNOWN])
    assert len(request_validated(rec,[],3)[2])==1
    assert len(rec.requests)==1


def test_exhaustion_retains_all_invalid_answers_and_never_synthesizes_a_stage():
    rec=observer(['{"grasp":"held"}',UNKNOWN[:-1]])
    with pytest.raises(ObservationValidationError) as error:
        request_validated(rec,[],2)
    assert len(error.value.attempts)==2 and all(not x['valid'] for x in error.value.attempts)


def test_explicit_length_rejects_even_complete_json():
    rec=observer([UNKNOWN],finish='length')
    with pytest.raises(ObservationValidationError):request_validated(rec,[],1)
