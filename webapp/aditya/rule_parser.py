# rule_parser.py (updated)
import re
import json
from typing import List

class RuleParser:
    def __init__(self):
        self.INDIAN_JOBS = [
            "farmer", "engineer", "software developer", "doctor", "nurse",
            "teacher", "professor", "student", "labourer", "shopkeeper",
            "manager", "police", "soldier", "army", "government employee",
            "civil servant", "artisan", "fisherman", "driver", "chef",
            "electrician", "plumber", "carpenter", "accountant", "banker",
            "business owner", "entrepreneur", "cleaner", "security guard",
            "architect", "journalist", "photographer", "lawyer", "advocate",
            "researcher", "scientist", "delivery agent", "rickshaw puller",
            "tailor", "mechanic", "welder", "data entry operator", "clerk",
            "home maker", "housewife", "unemployed", "retired"
        ]

        self.patterns = {
            'age_between': r'(?:age(?:d)?\s*(?:of)?\s*)?(?:between|from)\s*(\d{1,3})\s*(?:-|–|—|\sto\s|and)\s*(\d{1,3})',
            'age_simple_range': r'(\d{1,3})\s*(?:-|–|—)\s*(\d{1,3})\s*(?:years?)?',
            'age_min': r'(?:age\s*|applicant\s*|applicants\s*|applicant\'s\s*)?(?:over|above|at least|>=)\s*(\d{1,3})',
            'age_max': r'(?:age\s*|applicant\s*|applicants\s*|applicant\'s\s*)?(?:under|below|less than|<=|not exceeding)\s*(\d{1,3})',
            'income_max': r'(?:family\'s\s+|annual\s+|annual\s+family\s+|family\s+annual\s+)?(?:income|earnings|annual income|family income|total family income)\s*(?:should be|should not exceed|should not be more than|should be less than|is|are|:)?\s*(?:less than|below|under|not exceeding)?\s*(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d+)?)\s*(?:lakh|lakhs|lacs|thousand|k|per annum|per year|/year|pa|p\.a\.|annum)?',
            'income_min': r'(?:income|earnings|annual income|family income)\s*(?:should be|should exceed|must be|more than|over)\s*(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d+)?)',
            'gender_keywords': r'\b(women|woman|female|widow|widows|men|man|male)\b',
            'location_regex': r'\bresident\s+(?:of|in)?\s+([A-Z]?[a-zA-Z0-9&\-\s]+?)(?:[\.\n,;]|$)',
            # capture whole phrase before "are not eligible" or "not eligible for"
            'not_eligible_for': r'([A-Za-z0-9\s\-\&]+?)\s+(?:are|is|were|being|be)\s+not\s+eligible|not\s+eligible\s+for\s+([A-Za-z0-9\s\-\&]+)',
            'requires_bank_account': r'(?:should have|must have|requires?)\s+(?:a\s+)?(?:savings\s+bank\s+account|bank account|post office savings bank account|bank account with an aadhaar link)',
        }

        job_pattern = '|'.join(re.escape(job) for job in self.INDIAN_JOBS)
        self.patterns['occupation_regex'] = r'\b(' + job_pattern + r')(?:s)?\b'

        self.compiled_patterns = {k: re.compile(v, re.IGNORECASE) for k, v in self.patterns.items()}

    def _clean_amount(self, amt_str):
        if amt_str is None:
            return None
        s = str(amt_str).replace(',', '').strip()
        try:
            if '.' in s:
                return float(s)
            return int(s)
        except ValueError:
            return None

    # --- PARSING HELPERS ---

    def _parse_age(self, text: str) -> List[dict]:
        rules = []
        m = self.compiled_patterns['age_between'].search(text)
        if m:
            a = self._clean_amount(m.group(1)); b = self._clean_amount(m.group(2))
            if a is not None and b is not None:
                rules.append({"field": "age", "op": ">=", "value": int(a)})
                rules.append({"field": "age", "op": "<=", "value": int(b)})
                return rules
        m = self.compiled_patterns['age_simple_range'].search(text)
        if m:
            a = self._clean_amount(m.group(1)); b = self._clean_amount(m.group(2))
            if a is not None and b is not None:
                rules.append({"field": "age", "op": ">=", "value": int(a)})
                rules.append({"field": "age", "op": "<=", "value": int(b)})
                return rules
        m = self.compiled_patterns['age_min'].search(text)
        if m:
            a = self._clean_amount(m.group(1))
            if a is not None:
                rules.append({"field": "age", "op": ">=", "value": int(a)})
        m = self.compiled_patterns['age_max'].search(text)
        if m:
            a = self._clean_amount(m.group(1))
            if a is not None:
                rules.append({"field": "age", "op": "<=", "value": int(a)})
        return rules

    def _parse_income(self, text: str) -> List[dict]:
        rules = []
        m = self.compiled_patterns['income_max'].search(text)
        if m:
            amt = self._clean_amount(m.group(1))
            if amt is not None:
                rules.append({"field": "income", "op": "<=", "value": amt})
        m = self.compiled_patterns['income_min'].search(text)
        if m:
            amt = self._clean_amount(m.group(1))
            if amt is not None:
                rules.append({"field": "income", "op": ">=", "value": amt})
        return rules

    def _normalize_token(self, s: str) -> str:
        s = s.lower().strip()
        # remove trailing 'state' word and extra spaces
        s = re.sub(r'\s+state$', '', s, flags=re.IGNORECASE).strip()
        # basic singularization: drop trailing 's' if it's a simple plural
        if s.endswith('s') and len(s) > 3:
            s = s[:-1]
        return s

    def _parse_categorical(self, text: str) -> List[dict]:
        rules = []

        # FIRST: detect explicit negative eligibility groups and build excluded set
        excluded = set()
        for m in self.compiled_patterns['not_eligible_for'].finditer(text):
            group = (m.group(1) or m.group(2) or "").strip()
            if not group:
                continue
            # split on commas or the word 'and' (as a word)
            parts = re.split(r',|\band\b', group, flags=re.IGNORECASE)
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                norm = self._normalize_token(part)
                if norm:
                    excluded.add(norm)

        # Occupation mentions
        occs = self.compiled_patterns['occupation_regex'].findall(text)
        occ_norms = sorted({self._normalize_token(o) for o in occs if o})
        # If some occupations are listed but also in excluded set, avoid emitting positive 'in' for them
        positive_occs = [o for o in occ_norms if o not in excluded]
        if positive_occs:
            rules.append({"field": "occupation", "op": "in", "value": positive_occs})

        if excluded:
            # emit a single exclusion rule for occupations (as 'not_in')
            rules.append({"field": "occupation", "op": "not_in", "value": sorted(list(excluded))})

        # Gender
        genders = self.compiled_patterns['gender_keywords'].findall(text)
        if genders:
            lowered = [g.lower() for g in genders]
            if any(k in lowered for k in ('female', 'women', 'woman', 'widow', 'widows')):
                rules.append({"field": "gender", "op": "==", "value": "female"})
            elif any(k in lowered for k in ('male', 'men', 'man')):
                rules.append({"field": "gender", "op": "==", "value": "male"})

        # Location detection
        loc = self.compiled_patterns['location_regex'].search(text)
        if loc:
            location = loc.group(1).strip()
            location = re.sub(r'\s+state$', '', location, flags=re.IGNORECASE).strip()
            rules.append({"field": "location", "op": "in", "value": [location.lower()]})

        # Bank account/document requirements
        if self.compiled_patterns['requires_bank_account'].search(text):
            rules.append({"field": "has_bank_account", "op": "==", "value": True})

        return rules

    def parse_text(self, text: str):
        original_text = text
        text = text.strip()
        conditions = []
        confidence = 1.0

        conditions.extend(self._parse_age(text))
        conditions.extend(self._parse_income(text))
        conditions.extend(self._parse_categorical(text))

        print("\n--- PARSER DEBUG ---")
        print(f"Input Text (first 200 chars): {original_text[:200]!r}")
        print(f"Rules Found (Count: {len(conditions)}):")
        print(json.dumps(conditions, indent=4))
        print("--------------------")

        if not conditions:
            confidence = 0.0

        rule_structure = {"all": conditions}
        return rule_structure, confidence

