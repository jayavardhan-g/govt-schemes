#!/usr/bin/env python3
"""
show_rules.py

Run the RuleParser against all schemes in schemes_data.SAMPLE_SCHEMES and:
 - Print a readable listing of parsed rules per scheme
 - Save a JSON report with the ASTs and parser confidence
"""
import json
import argparse
import sys
from pathlib import Path

# ensure project root is importable when running from tests/ or other cwd
sys.path.insert(0, str(Path(__file__).resolve().parents[0]))

from rule_parser import RuleParser
from schemes_data import SAMPLE_SCHEMES


def main():
    p = argparse.ArgumentParser(description="Run RuleParser on all SAMPLE_SCHEMES and display the rules.")
    p.add_argument("--output", "-o", default="scheme_rules_output.json", help="JSON output path")
    p.add_argument("--min-confidence", "-c", type=float, default=0.0, help="Only include schemes with parser confidence >= this")
    p.add_argument("--only-parsed", action="store_true", help="Only print schemes that produced >=1 rule")
    p.add_argument("--pretty", action="store_true", help="Pretty-print JSON fields in output file")
    args = p.parse_args()

    rp = RuleParser()

    results = []
    printed = 0

    for i, scheme in enumerate(SAMPLE_SCHEMES):
        title = scheme.get("title") or f"<untitled {i}>"
        desc = scheme.get("description") or ""
        state = scheme.get("state", "")
        source = scheme.get("source_url", "")

        rule_ast, conf = rp.parse_text(desc)

        entry = {
            "index": i,
            "title": title,
            "state": state,
            "source_url": source,
            "confidence": conf,
            "num_rules": len(rule_ast.get("all", [])),
            "rule_ast": rule_ast
        }
        results.append(entry)

        if conf < args.min_confidence:
            # skip printing entries below confidence threshold
            continue
        if args.only_parsed and entry["num_rules"] == 0:
            continue

        printed += 1
        print("=" * 80)
        print(f"[{i}] {title}")
        if state:
            print(f"  State: {state}")
        if source:
            print(f"  Source: {source}")
        print(f"  Parser confidence: {conf:.2f}")
        print(f"  Rules found: {entry['num_rules']}")
        if entry["num_rules"] == 0:
            print("  (no rules extracted)")
        else:
            # pretty print the rule AST for human inspection
            print("  Rule AST:")
            print(json.dumps(entry["rule_ast"], indent=4, ensure_ascii=False))
        print("=" * 80)
        print()

    # write JSON file with all results
    out_path = Path(args.output)
    if args.pretty:
        dump_kw = {"ensure_ascii": False, "indent": 2}
    else:
        dump_kw = {"ensure_ascii": False}
    out_path.write_text(json.dumps({"total": len(results), "results": results}, **dump_kw), encoding="utf-8")
    print(f"Wrote JSON report to: {out_path.resolve()}")
    print(f"Printed {printed} schemes (out of {len(results)}).")


if __name__ == "__main__":
    main()

