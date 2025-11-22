# webapp/matcher.py
import json
from db import db
from models import Scheme, SchemeRule

def evaluate_rule(rule, profile):
    """Return True/False for atomic rule JSON. Supports 'all' and 'any' and atomic ops."""
    if rule is None:
        return False
    if 'all' in rule:
        return all(evaluate_rule(r, profile) for r in rule['all'])
    if 'any' in rule:
        return any(evaluate_rule(r, profile) for r in rule['any'])
    # atomic
    field = rule.get('field')
    op = rule.get('op')
    value = rule.get('value')
    user_val = profile.get(field)
    # normalize
    if user_val is None:
        return False
    # numeric comparisons
    if op in ['<','<=','>','>=']:
        try:
            uv = float(user_val)
            vv = float(value)
        except:
            return False
        if op == '<': return uv < vv
        if op == '<=': return uv <= vv
        if op == '>': return uv > vv
        if op == '>=': return uv >= vv
    if op == '==':
        return str(user_val).lower() == str(value).lower()
    if op == 'in':
        # value expected list
        return str(user_val).lower() in [str(v).lower() for v in value]
    return False


def evaluate_rules_for_profile(profile):
    """
    Returns list of results for all schemes using SQLAlchemy models.
    """
    schemes = Scheme.query.order_by(Scheme.title).all()
    results = []
    for s in schemes:
        rules = SchemeRule.query.filter_by(scheme_id=s.id).all()
        passed = False
        score = 0.0
        reasons = {}
        if rules:
            for r in rules:
                try:
                    rule_obj = r.rule_json
                    ok = evaluate_rule(rule_obj, profile)
                    if ok:
                        passed = True
                        score = 1.0
                        reasons = {'snippet': r.snippet}
                        break
                except Exception as e:
                    reasons = {'error': str(e)}
        else:
            reasons = {'note': 'No rule available'}
        results.append({
            'scheme_id': s.id,
            'title': s.title,
            'description': s.description,
            'result': 'eligible' if passed else 'not eligible',
            'score': score,
            'reasons': reasons
        })
    results = sorted(results, key=lambda x: (-x['score'], x['title']))
    return results
