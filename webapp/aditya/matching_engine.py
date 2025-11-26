class MatchingEngine:
    """
    Evaluate rule AST against a profile. Supports numeric and categorical comparisons,
    plus 'in' and 'not_in'.
    """

    def _safe_cast_number(self, v):
        """Try to cast to float/int, otherwise return None."""
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
        field = rule['field']
        op = rule['op']
        value = rule['value']

        profile_value = profile.get(field)

        # missing field
        if profile_value is None:
            status = False
            explanation = f"FAIL: Your profile is missing the required field '{field}'."
            return {"rule": f"{field} {op} {value}", "status": status, "profile_value": profile_value, "explanation": explanation}

        # Numeric comparisons
        if op in (">", "<", ">=", "<="):
            rule_num = self._safe_cast_number(value)
            prof_num = self._safe_cast_number(profile_value)
            if rule_num is None or prof_num is None:
                status = False
                explanation = f"FAIL: Could not compare numeric values for '{field}'."
            else:
                if op == ">":
                    status = prof_num > rule_num
                elif op == "<":
                    status = prof_num < rule_num
                elif op == ">=":
                    status = prof_num >= rule_num
                elif op == "<=":
                    status = prof_num <= rule_num
                explanation = f"{'PASS' if status else 'FAIL'}: Your {field} ({profile_value}) {op} {value}."
            return {"rule": f"{field} {op} {value}", "status": status, "profile_value": profile_value, "explanation": explanation}

        # 'in' and 'not_in' (categorical)
        if op in ("in", "not_in"):
            # normalize profile value and rule list
            if isinstance(profile_value, list):
                prof_values = [str(x).lower() for x in profile_value]
            else:
                prof_values = [str(profile_value).lower()]

            if isinstance(value, list):
                rule_values = [str(x).lower() for x in value]
            else:
                rule_values = [str(value).lower()]

            if op == "in":
                # success if any of the profile entries matches any rule value
                status = any(pv in rule_values for pv in prof_values)
                explanation = f"{'PASS' if status else 'FAIL'}: Your {field} ({profile_value}) {'is' if status else 'is not'} in required set {value}."
            else:  # not_in
                status = not any(pv in rule_values for pv in prof_values)
                explanation = f"{'PASS' if status else 'FAIL'}: Your {field} ({profile_value}) {'is not' if status else 'is'} allowed by exclusion list {value}."

            return {"rule": f"{field} {op} {value}", "status": status, "profile_value": profile_value, "explanation": explanation}

        # boolean or equality
        if op == "==":
            # handle booleans specially
            if isinstance(value, bool):
                # try to coerce profile value to boolean-ish
                prof_bool = bool(profile_value)
                status = prof_bool == value
                explanation = f"{'PASS' if status else 'FAIL'}: Your {field} ({profile_value}) matches required value {value}."
            else:
                status = str(profile_value).lower() == str(value).lower()
                explanation = f"{'PASS' if status else 'FAIL'}: Your {field} ({profile_value}) matches required value {value}."
            return {"rule": f"{field} {op} {value}", "status": status, "profile_value": profile_value, "explanation": explanation}

        if op == "!=":
            status = str(profile_value).lower() != str(value).lower()
            explanation = f"{'PASS' if status else 'FAIL'}: Your {field} ({profile_value}) must not be {value}."
            return {"rule": f"{field} {op} {value}", "status": status, "profile_value": profile_value, "explanation": explanation}

        # unsupported operator
        status = False
        explanation = f"ERROR: Unsupported operator '{op}'."
        return {"rule": f"{field} {op} {value}", "status": status, "profile_value": profile_value, "explanation": explanation}

    def evaluate(self, profile: dict, rule_ast: dict) -> tuple:
        rules_list = rule_ast.get("all", [])
        total_rules = len(rules_list)
        passing_rules = 0
        outcomes = []

        for r in rules_list:
            out = self._evaluate_rule(profile, r)
            outcomes.append(out)
            if out['status']:
                passing_rules += 1

        if total_rules == 0:
            final_eligibility = False
            score = 0.0
        else:
            final_eligibility = (passing_rules == total_rules)
            score = passing_rules / total_rules

        summary = "✅ ELIGIBLE" if final_eligibility else "❌ INELIGIBLE"
        explanation_lines = [
            f"### {summary} for Scheme:",
            f"**Overall Score**: {score:.2f} ({passing_rules} out of {total_rules} rules passed).",
            "---",
            "### Detailed Rule Breakdown:"
        ]
        for o in outcomes:
            explanation_lines.append(f"* {o['explanation']}")

        if not final_eligibility:
            explanation_lines.append(f"\n**Reason for ineligibility**: {total_rules - passing_rules} rule(s) failed.")

        final_explanation = "\n".join(explanation_lines)
        return final_eligibility, final_explanation, score

