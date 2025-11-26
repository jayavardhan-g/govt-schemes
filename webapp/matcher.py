# webapp/matcher.py
import json
from db import db
from models import Scheme, SchemeRule

# ==========================================
# PART 1: Friend's Matching Logic (UPDATED)
# ==========================================
class MatchingEngine:
    """
    Evaluate rule AST against a profile. 
    UPDATED: Treats missing fields as 'Skipped' (Neutral) instead of 'Failed'.
    """

    def _safe_cast_number(self, v):
        if v is None: return None
        if isinstance(v, (int, float)): return v
        s = str(v).replace(',', '').strip()
        try:
            if '.' in s: return float(s)
            return int(s)
        except ValueError:
            try: return float(s)
            except ValueError: return None

    def _evaluate_rule(self, profile: dict, rule: dict) -> dict:
        field = rule.get('field')
        op = rule.get('op')
        value = rule.get('value')

        profile_value = profile.get(field)

        # --- FIX: Handle Missing Field as NEUTRAL, not FAILURE ---
        if profile_value is None:
            status = None  # Changed from False to None
            explanation = f"SKIPPED: Profile missing field '{field}'."
            # We return skipped=True so the UI knows to show it as gray/neutral
            return {"rule": f"{field} {op} {value}", "status": None, "profile_value": None, "explanation": explanation, "skipped": True}

        # Numeric comparisons
        if op in (">", "<", ">=", "<="):
            rule_num = self._safe_cast_number(value)
            prof_num = self._safe_cast_number(profile_value)
            
            if rule_num is None or prof_num is None:
                status = False
                explanation = f"FAIL: Non-numeric values for '{field}'."
            else:
                if op == ">": status = prof_num > rule_num
                elif op == "<": status = prof_num < rule_num
                elif op == ">=": status = prof_num >= rule_num
                elif op == "<=": status = prof_num <= rule_num
                else: status = False
                explanation = f"{'PASS' if status else 'FAIL'}: {field} ({prof_num}) {op} {rule_num}."
            
            return {"rule": f"{field} {op} {value}", "status": status, "profile_value": profile_value, "explanation": explanation, "skipped": False}

        # Categorical (In / Not In)
        if op in ("in", "not_in"):
            if isinstance(profile_value, list):
                prof_values = [str(x).lower() for x in profile_value]
            else:
                prof_values = [str(profile_value).lower()]

            if isinstance(value, list):
                rule_values = [str(x).lower() for x in value]
            else:
                rule_values = [str(value).lower()]

            if op == "in":
                status = any(pv in rule_values for pv in prof_values)
                explanation = f"{'PASS' if status else 'FAIL'}: {field} ({profile_value}) {'in' if status else 'not in'} {value}."
            else:  # not_in
                status = not any(pv in rule_values for pv in prof_values)
                explanation = f"{'PASS' if status else 'FAIL'}: {field} ({profile_value}) exclusion check."

            return {"rule": f"{field} {op} {value}", "status": status, "profile_value": profile_value, "explanation": explanation, "skipped": False}

        # Equality
        if op == "==":
            if isinstance(value, bool):
                status = bool(profile_value) == value
            else:
                status = str(profile_value).lower() == str(value).lower()
            
            explanation = f"{'PASS' if status else 'FAIL'}: {field} matches {value}."
            return {"rule": f"{field} {op} {value}", "status": status, "profile_value": profile_value, "explanation": explanation, "skipped": False}

        if op == "!=":
            status = str(profile_value).lower() != str(value).lower()
            explanation = f"{'PASS' if status else 'FAIL'}: {field} does not match {value}."
            return {"rule": f"{field} {op} {value}", "status": status, "profile_value": profile_value, "explanation": explanation, "skipped": False}

        return {"rule": f"{field} {op} {value}", "status": False, "profile_value": profile_value, "explanation": f"Unknown op {op}", "skipped": False}

    def evaluate(self, profile: dict, rule_ast: dict) -> tuple:
        """
        Returns (final_eligibility_bool, score_float, outcomes_list)
        """
        if 'any' in rule_ast:
             rules_list = rule_ast.get("any", [])
             mode = 'any'
        else:
             rules_list = rule_ast.get("all", [])
             mode = 'all'

        total_rules = len(rules_list)
        passing_rules = 0
        failed_rules = 0  # Track explicit failures
        outcomes = []

        if total_rules == 0:
            return False, 0.0, [{"error": "Empty rule set"}]

        for r in rules_list:
            out = self._evaluate_rule(profile, r)
            out['atom'] = r 
            out['msg'] = out['explanation']
            outcomes.append(out)
            
            if out['skipped']:
                continue # Don't count as pass OR fail
            
            if out['status']:
                passing_rules += 1
            else:
                failed_rules += 1

        # --- SCORE CALCULATION ---
        # Score = Passed / Total. 
        # Note: Skipped items lower the score (preventing 100%), but they don't cause 0%.
        score = passing_rules / total_rules if total_rules > 0 else 0.0
        
        # --- FINAL DETERMINATION ---
        if mode == 'any':
            # Eligible if at least one passed
            final_eligibility = (passing_rules > 0)
        else: # mode == 'all'
            # Eligible if NOTHING EXPLICITLY FAILED.
            # If failed_rules > 0, they are definitely not eligible.
            # If failed_rules == 0 but skipped > 0, they are "Maybe Eligible" (which we treat as True here, handled by UI label)
            final_eligibility = (failed_rules == 0)

        return final_eligibility, score, outcomes


# ==========================================
# PART 2: Database Integration
# ==========================================

engine = MatchingEngine()

def evaluate_rule_with_details(rule, profile):
    try:
        passed, score, details = engine.evaluate(profile, rule)
        return passed, score, details
    except Exception as e:
        return False, 0.0, [{'error': str(e)}]

def evaluate_rules_for_profile(profile):
    schemes = Scheme.query.order_by(Scheme.title).all()
    results = []

    for s in schemes:
        rules = SchemeRule.query.filter_by(scheme_id=s.id).all()
        best_score = -1.0
        best_passed = False
        best_details = {'note': 'No rule available'}

        if rules:
            for r in rules:
                try:
                    rule_obj = r.rule_json
                    passed, score, details = evaluate_rule_with_details(rule_obj, profile)
                    
                    # We prefer the rule that gives the HIGHEST score
                    if score > best_score:
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
            best_score = 0.0

        if best_score < 0: best_score = 0.0
        score_percent = float(best_score) * 100.0

        # --- LABEL LOGIC ---
        skipped_any = False
        failed_any = False
        
        if 'evaluations' in best_details and isinstance(best_details['evaluations'], list):
             skipped_any = any(d.get('skipped') for d in best_details['evaluations'])
             failed_any = any(d.get('status') is False for d in best_details['evaluations'])

        if failed_any:
            label = 'Not Eligible' # Explicit failure
        elif best_score >= 1.0:
            label = 'Eligible' # 100% match, nothing skipped
        elif skipped_any and not failed_any:
            label = 'Maybe Eligible' # No failures, but missing data
        else:
            label = 'Not Eligible' # Fallback

        results.append({
            'scheme_id': s.id,
            'title': s.title,
            'description': s.description,
            'result': label,
            'score': round(score_percent, 2),
            'reasons': best_details
        })

    results = sorted(results, key=lambda x: (-x['score'], x['title']))
    return results


def evaluate_rule(rule, profile):
    """
    Backwards-compatible boolean API (returns True if rule passes).
    """
    passed, score, details = evaluate_rule_with_details(rule, profile)
    return bool(passed)