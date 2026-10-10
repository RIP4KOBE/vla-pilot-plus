"""Closed engineering-family routing; selection never grants admission."""
from scripts import qd_ed_n36_engineering as parent


def for_plan(plan):
    from scripts import qd_ed_n36_engineering_r1 as recovery
    if plan.get('schema') == parent.PLAN_SCHEMA:
        for api in (parent, recovery):
            if plan.get('cohort') == api.IDENTITY:
                return api
    elif plan.get('schema') == parent.AUDIT_SCHEMA:
        scope = parent.read(plan['scope'])
        for api in (parent, recovery):
            if scope.get('specification') == api.SPECIFICATION:
                api.validate_scope_reference(plan['scope'])
                return api
    raise ValueError('unknown engineering identity/specification')
