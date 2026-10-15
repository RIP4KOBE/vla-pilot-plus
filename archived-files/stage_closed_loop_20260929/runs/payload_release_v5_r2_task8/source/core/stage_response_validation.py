"""Bounded re-request of malformed visual observations, never semantic retries."""


class ObservationValidationError(ValueError):
    def __init__(self, attempts):
        super().__init__('No complete schema-valid observation within the request limit')
        self.attempts=attempts


def request_validated(observer, content, limit):
    from core.stage_evidence import parse_observation
    if isinstance(limit,bool) or not isinstance(limit,int) or not 1 <= limit <= 3:
        raise ValueError('observation validation limit must be an integer in [1,3]')
    attempts=[]
    for index in range(limit):
        raw=observer._request_stage_response(content)
        completion=getattr(observer,'_last_completion_metadata',None)
        item=dict(attempt=index+1,raw_response=raw,completion_metadata=completion,
                  capture_query_index=getattr(observer,'cursor',0)-1)
        try:
            if (completion or {}).get('finish_reason')=='length':
                raise ValueError('truncated observation')
            observation=parse_observation(raw)
        except (ValueError,TypeError) as exc:
            item.update(valid=False,error_type=type(exc).__name__)
            attempts.append(item)
            continue
        item['valid']=True;attempts.append(item)
        # The first valid answer wins, including uncertain or negative answers.
        return raw,observation,attempts
    raise ObservationValidationError(attempts)
