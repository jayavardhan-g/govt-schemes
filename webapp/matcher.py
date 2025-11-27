"""
Eligibility matching engine for government schemes.

Core logic for evaluating user profiles against parsed eligibility rules.
Supports numeric comparisons, categorical matching, and boolean logic (AND/OR).
"""

import json
from db import db
from models import Scheme, SchemeRule

# ===== ELIGIBILITY RULE EVALUATION ENGINE =====

class MatchingEngine:
    """
    Evaluates eligibility rules (in JSON AST format) against user profiles.
    
    Key design: Missing profile fields are treated as SKIPPED (neutral) rather than failures,
    allowing "Maybe Eligible" outcomes when some data is incomplete.
    """

    def _safe_cast_number(self, v):
        """Convert value to int/float safely, handling commas and mixed types."""
        if v is None: 
            return None
        if isinstance(v, (int, float)): 
            return v
        s = str(v).replace(',', '').strip()
        try:
            if '.' in s: 
                return float(s)
            return int(s)
        except ValueError:
            try: 
                return float(s)
            except ValueError: 
                return None

    def _evaluate_rule(self, profile: dict, rule: dict) -> dict:
        """Evaluate a single atomic rule against profile data."""
        field = rule.get('field')
        op = rule.get('op')
        value = rule.get('value')

        profile_value = profile.get(field)

        # Missing field: mark as skipped rather than failed
        # This allows "Maybe Eligible" outcomes when user hasn't filled all fields
        if profile_value is None:
            status = None  
            explanation = f"SKIPPED: Profile missing field '{field}'."
            return {
                "rule": f"{field} {op} {value}", 
                "status": None, 
                "profile_value": None, 
                "explanation": explanation, 
                "skipped": True
            }

        # Numeric range comparisons (>, <, >=, <=)
        if op in (">", "<", ">=", "<="):
            rule_num = self._safe_cast_number(value)
            prof_num = self._safe_cast_number(profile_value)
            
            if rule_num is None or prof_num is None:
                status = False
                explanation = f"FAIL: Non-numeric values for '{field}'."
            else:
                if op == ">": 
                    status = prof_num > rule_num
                elif op == "<": 
                    status = prof_num < rule_num
                elif op == ">=": 
                    status = prof_num >= rule_num
                elif op == "<=": 
                    status = prof_num <= rule_num
                else: 
                    status = False
                explanation = f"{'PASS' if status else 'FAIL'}: {field} ({prof_num}) {op} {rule_num}."
            
            return {
                "rule": f"{field} {op} {value}", 
                "status": status, 
                "profile_value": profile_value, 
                "explanation": explanation, 
                "skipped": False
            }

        # Set membership checks (in / not_in)
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
                explanation = f"{'PASS' if status else 'FAIL'}: {field} ({profile_value}) {'is' if status else 'is not'} in required set {value}."
            else:  # not_in
                status = not any(pv in rule_values for pv in prof_values)
                explanation = f"{'PASS' if status else 'FAIL'}: {field} ({profile_value}) exclusion check passed."

            return {
                "rule": f"{field} {op} {value}", 
                "status": status, 
                "profile_value": profile_value, 
                "explanation": explanation, 
                "skipped": False
            }

        # Equality tests (== / !=)
        if op == "==":
            if isinstance(value, bool):
                status = bool(profile_value) == value
            else:
                status = str(profile_value).lower() == str(value).lower()
            
            explanation = f"{'PASS' if status else 'FAIL'}: {field} matches {value}."
            return {
                "rule": f"{field} {op} {value}", 
                "status": status, 
                "profile_value": profile_value, 
                "explanation": explanation, 
                "skipped": False
            }

        if op == "!=":
            status = str(profile_value).lower() != str(value).lower()
            explanation = f"{'PASS' if status else 'FAIL'}: {field} does not match {value}."
            return {
                "rule": f"{field} {op} {value}", 
                "status": status, 
                "profile_value": profile_value, 
                "explanation": explanation, 
                "skipped": False
            }

        # Unsupported operator
        return {
            "rule": f"{field} {op} {value}", 
            "status": False, 
            "profile_value": profile_value, 
            "explanation": f"ERROR: Unknown operator '{op}'", 
            "skipped": False
        }

    def evaluate(self, profile: dict, rule_ast: dict) -> tuple:
        """
        Evaluate complete rule AST against profile.
        
        Returns:
            - final_eligibility (bool): Overall eligibility determination
            - score (float): 0.0-1.0 matching score
            - outcomes (list): Detail for each individual rule
        """
        if 'any' in rule_ast:
            rules_list = rule_ast.get("any", [])
            mode = 'any'  # OR logic
        else:
            rules_list = rule_ast.get("all", [])
            mode = 'all'  # AND logic

        total_rules = len(rules_list)
        passing_rules = 0
        failed_rules = 0  # Track explicit rule failures
        outcomes = []

        if total_rules == 0:
            return False, 0.0, [{"error": "Empty rule set"}]

        # Evaluate each atomic rule
        for r in rules_list:
            out = self._evaluate_rule(profile, r)
            out['atom'] = r 
            out['msg'] = out['explanation']
            outcomes.append(out)
            
            # Skipped rules don't affect pass/fail counts
            if out['skipped']:
                continue 
            
            # Track passes and failures
            if out['status']:
                passing_rules += 1
            else:
                failed_rules += 1

        # ===== SCORE CALCULATION =====
        # Score ranges from 0-1 based on passing rules
        # Skipped items reduce score but don't cause complete failure
        score = passing_rules / total_rules if total_rules > 0 else 0.0
        
        # ===== FINAL ELIGIBILITY DETERMINATION =====
        if mode == 'any':
            # OR logic: eligible if ANY rule passed
            final_eligibility = (passing_rules > 0)
        else:  # mode == 'all'
            # AND logic: eligible if NOTHING explicitly failed
            # If failed_rules > 0, definitely not eligible
            # If failed_rules == 0 but skipped > 0, "Maybe Eligible"
            final_eligibility = (failed_rules == 0)

        # # DEBUG: Log eligibility calculation
        # print(f"[DEBUG] Mode={mode}, Passed={passing_rules}, Failed={failed_rules}, Score={score}, Final={final_eligibility}")

        return final_eligibility, score, outcomes


# ===== DATABASE INTEGRATION =====

# Global engine instance
engine = MatchingEngine()

def evaluate_rule_with_details(rule, profile):
    """
    Wrapper for engine.evaluate() with error handling.
    Returns: (passed, score, details)
    """
    try:
        passed, score, details = engine.evaluate(profile, rule)
        return passed, score, details
    except Exception as e:
        # # DEBUG: Log evaluation errors
        # print(f"[ERROR] Rule evaluation failed: {e}")
        return False, 0.0, [{'error': str(e)}]

def evaluate_rules_for_profile(profile):
    """
    Evaluate all schemes against a user profile.
    Returns sorted list of matching results with scores.
    """
    # Fetch all schemes from database
    schemes = Scheme.query.order_by(Scheme.title).all()
    results = []

    for s in schemes:
        # Get eligibility rules for this scheme
        rules = SchemeRule.query.filter_by(scheme_id=s.id).all()
        best_score = -1.0
        best_passed = False
        best_details = {'note': 'No eligibility rule defined yet'}

        if rules:
            # Evaluate all rules for this scheme, keep the best match
            for r in rules:
                try:
                    rule_obj = r.rule_json
                    passed, score, details = evaluate_rule_with_details(rule_obj, profile)
                    
                    # Use rule with highest score (closest match)
                    if score > best_score:
                        best_score = score
                        best_passed = passed
                        best_details = {
                            'snippet': getattr(r, 'snippet', None),
                            'parser_confidence': getattr(r, 'parser_confidence', None),
                            'rule_id': getattr(r, 'id', None),
                            'evaluations': details
                        }
                        # # DEBUG: Log best match found
                        # print(f"[DEBUG] Scheme {s.id}: New best score {best_score} with confidence {best_details.get('parser_confidence')}")
                except Exception as e:
                    best_details = {'error': str(e)}
        else:
            best_score = 0.0

        if best_score < 0: 
            best_score = 0.0
        
        # Convert to percentage
        score_percent = float(best_score) * 100.0

        # ===== ELIGIBILITY LABEL LOGIC =====
        skipped_any = False
        failed_any = False
        
        if 'evaluations' in best_details and isinstance(best_details['evaluations'], list):
            skipped_any = any(d.get('skipped') for d in best_details['evaluations'])
            failed_any = any(d.get('status') is False for d in best_details['evaluations'])

        # Determine eligibility label
        if failed_any:
            label = 'Not Eligible'  # Explicit failure
        elif best_score >= 1.0:
            label = 'Eligible'  # Perfect match
        elif skipped_any and not failed_any:
            label = 'Maybe Eligible'  # Missing data but no explicit failures
        else:
            label = 'Not Eligible'  # Fallback

        results.append({
            'scheme_id': s.id,
            'title': s.title,
            'description': s.description,
            'result': label,
            'score': round(score_percent, 2),
            'reasons': best_details
        })

    # Sort by score (highest first), then alphabetically by title
    results = sorted(results, key=lambda x: (-x['score'], x['title']))
    # # DEBUG: Log final results
    # print(f"[DEBUG] Generated {len(results)} results for profile")
    return results


def evaluate_rule(rule, profile):
    """
    Simple boolean API for basic eligibility check (True if passes).
    Kept for backwards compatibility.
    """
    passed, score, details = evaluate_rule_with_details(rule, profile)
    return bool(passed)
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