# webapp/matcher.py
import os
import json
from db import db
from models import Scheme, SchemeRule

# Behavior:
# - For 'all' rules:
#     * If any non-skipped atom explicitly FAILS -> rule score = 0.0 (Not Eligible)
#     * Else score = passed_count / total_atoms  (skipped atoms count in denominator, preventing 100%)
# - For 'any' rules:
#     * If at least one non-skipped atom passes -> candidate passes; score = passed_count / total_atoms
#     * If none pass -> score = 0.0
# - Detailed per-atom evaluations are returned for UI/inspection.

def _normalize_user_val(user_val):
    """Normalize empty strings to None and return trimmed values."""
    if user_val is None:
        return None
    if isinstance(user_val, str):
        u = user_val.strip()
        if u == '':
            return None
        return u
    return user_val


def _atomic_check(atom, profile):
    """
    Evaluate a single atomic rule.
    Returns a tuple: (status, msg, skipped)
      - status: True (pass) or False (fail) or None (skipped)
      - msg: human readable message
      - skipped: True if this atom was skipped due to missing profile field
    """
    field = atom.get('field')
    op = atom.get('op')
    value = atom.get('value')

    user_val = profile.get(field)
    user_val = _normalize_user_val(user_val)

    if user_val is None:
        # Missing field -> mark as skipped (we will still count it in total for 'all')
        return None, f"field '{field}' missing in profile -> SKIPPED", True

    # Numeric comparisons
    if op in ('<', '<=', '>', '>='):
        try:
            uv = float(user_val)
            vv = float(value)
        except Exception:
            return False, f"numeric comparison failed for field '{field}' (user='{user_val}', rule='{value}')", False
        if op == '<':
            return (uv < vv), f"{uv} < {vv}", False
        if op == '<=':
            return (uv <= vv), f"{uv} <= {vv}", False
        if op == '>':
            return (uv > vv), f"{uv} > {vv}", False
        if op == '>=':
            return (uv >= vv), f"{uv} >= {vv}", False

    # Equality
    if op == '==':
        passed = str(user_val).strip().lower() == str(value).strip().lower()
        return passed, (f"{user_val} == {value}" if passed else f"{user_val} != {value}"), False

    # Membership: support list membership with case-insensitive & substring matching
    if op == 'in':
        vals = value if isinstance(value, (list, tuple, set)) else [value]
        u = str(user_val).strip().lower()
        for v in vals:
            vs = str(v).strip().lower()
            if vs == u:
                return True, f"'{user_val}' equals '{v}'", False
            if vs in u:
                return True, f"'{v}' substring-match in '{user_val}'", False
        return False, f"'{user_val}' not in {vals}", False

    # Unknown operator
    return False, f"unknown operator '{op}'", False


def evaluate_rule_with_details(rule, profile):
    """
    Evaluate a rule and return tuple:
      (passed_bool, score_float_in_0_1, details_list)

    details_list contains dicts:
      { 'atom': <atom>, 'status': True/False/None, 'msg': <str>, 'skipped': True/False }
    """
    if rule is None:
        return False, 0.0, [{"error": "no rule provided"}]

    # handle 'all'
    if 'all' in rule:
        atoms = rule['all']
        details = []
        passed_count = 0
        failed_count = 0
        total = len(atoms) if isinstance(atoms, (list, tuple)) else 0
        if total == 0:
            return False, 0.0, [{"error": "empty 'all' clause"}]

        for atom in atoms:
            status, msg, skipped = _atomic_check(atom, profile)
            details.append({'atom': atom, 'status': status, 'msg': msg, 'skipped': bool(skipped)})
            if status:
                passed_count += 1
            elif status is False:
                failed_count += 1
            # skipped -> neither passed nor failed_count incremented

        # If any non-skipped atom explicitly failed -> hard fail -> score 0
        if failed_count > 0:
            return False, 0.0, details

        # No failures among provided inputs. Score uses total atoms (skipped counted),
        # so missing fields reduce the percent and prevent 100% unless all atoms actually passed.
        score = passed_count / total if total > 0 else 0.0
        passed = (passed_count == total)  # true only if every atom passed (no skips, no fails)
        return passed, score, details

    # handle 'any'
    if 'any' in rule:
        atoms = rule['any']
        details = []
        passed_count = 0
        total = len(atoms) if isinstance(atoms, (list, tuple)) else 0
        if total == 0:
            return False, 0.0, [{"error": "empty 'any' clause"}]

        for atom in atoms:
            status, msg, skipped = _atomic_check(atom, profile)
            details.append({'atom': atom, 'status': status, 'msg': msg, 'skipped': bool(skipped)})
            if status:
                passed_count += 1
            # skipped counts toward total but not passed_count

        passed_any = passed_count >= 1
        # Score reflects fraction of atoms that passed among total atoms (skips lower fraction)
        score = passed_count / total if total > 0 else 0.0
        return passed_any, score, details

    # atomic single rule
    status, msg, skipped = _atomic_check(rule, profile)
    if skipped:
        # missing -> treat as not passed (and counts toward denominator externally)
        return False, 0.0, [{'atom': rule, 'status': None, 'msg': msg, 'skipped': True}]
    # direct atomic pass/fail
    return bool(status), (1.0 if status else 0.0), [{'atom': rule, 'status': bool(status), 'msg': msg, 'skipped': False}]


def evaluate_rule(rule, profile):
    """
    Backwards-compatible boolean API (returns True if rule passes).
    """
    passed, score, details = evaluate_rule_with_details(rule, profile)
    return bool(passed)


def evaluate_rules_for_profile(profile):
    """
    Returns list of results for all schemes using SQLAlchemy models.

    Each result contains:
      - scheme_id, title, description
      - result: one of 'Eligible', 'Maybe Eligible', 'Not Eligible'
      - score: percent (0..100 float)
      - reasons: detailed dict including 'evaluations' (atoms), 'snippet', 'parser_confidence', etc.
    """
    schemes = Scheme.query.order_by(Scheme.title).all()
    results = []

    for s in schemes:
        rules = SchemeRule.query.filter_by(scheme_id=s.id).all()
        best_score = -1.0
        best_passed = False
        best_details = {'note': 'No rule available'}
        # Evaluate every rule and pick the one with highest score (prefer higher completeness)
        if rules:
            for r in rules:
                try:
                    rule_obj = r.rule_json
                    passed, score, details = evaluate_rule_with_details(rule_obj, profile)
                    # choose best by raw score; if equal prefer passed==True
                    if score > best_score or (score == best_score and passed and not best_passed):
                        best_score = score
                        best_passed = passed
                        best_details = {
                            'snippet': getattr(r, 'snippet', None),
                            'parser_confidence': getattr(r, 'parser_confidence', None),
                            'rule_id': getattr(r, 'id', None),
                            'evaluations': details
                        }
                except Exception as e:
                    best_details = {'error': str(e)}
        else:
            best_details = {'note': 'No rule available'}
            best_score = 0.0
            best_passed = False

        # Normalize best_score if never set
        if best_score < 0:
            best_score = 0.0

        # Determine result label:
        # - If score == 0.0 -> Not Eligible
        # - If score == 1.0 -> Eligible (all atoms present and passed)
        # - Else -> Maybe Eligible (partial match / missing fields)
        score_percent = float(best_score) * 100.0

        if best_score <= 0.0:
            label = 'Not Eligible'
        elif best_score >= 1.0:
            label = 'Eligible'
        else:
            label = 'Maybe Eligible'

        results.append({
            'scheme_id': s.id,
            'title': s.title,
            'description': s.description,
            'result': label,
            'score': round(score_percent, 2),   # percent with two decimals
            'reasons': best_details
        })

    # sort: higher score first, then title
    results = sorted(results, key=lambda x: (-x['score'], x['title']))
    return results
