#!/usr/bin/env python3
"""
Data pipeline orchestrator for web scraping and parsing.

Runs in sequence:
1. Fetcher: Downloads and renders government scheme websites
2. Parser: Extracts eligibility criteria from rendered HTML

Combined output feeds database seeding process.
"""

import sys
import os
from importlib import import_module

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

def run_fetcher():
    """Step 1: Download and render all website URLs."""
    print("\n============================")
    print(" STEP 1: Fetching HTML")
    print("============================")
    try:
        fetcher = import_module("fetcher")
    except Exception as e:
        print("Error: Could not import fetcher.py")
        print(e)
        sys.exit(1)

    # # DEBUG: Fetcher logging
    # print("[DEBUG] Starting HTML fetch process...")
    fetcher.main()
    # # DEBUG: Confirm fetch complete
    # print("[DEBUG] Fetcher completed successfully")
    print("Fetching completed.\n")


def run_parser():
    """Step 2: Parse HTML files and extract scheme data."""
    print("\n============================")
    print(" STEP 2: Parsing HTML")
    print("============================")
    try:
        parser = import_module("parser")
    except Exception as e:
        print("Error: Could not import parser.py")
        print(e)
        sys.exit(1)

    # # DEBUG: Parser logging
    # print("[DEBUG] Starting HTML parsing...")
    parser.parse_all_html()
    # # DEBUG: Confirm parse complete
    # print("[DEBUG] Parser completed successfully")
    print("Parsing completed.\n")


def main():
    """Execute full pipeline: fetch then parse."""
    print("[INFO] Starting government schemes data pipeline...")
    run_fetcher()
    run_parser()
    print("\n============================")
    print("  PIPELINE COMPLETE!")
    print("  Output locations:")
    print("  → output/raw_html/ (cached HTML)")
    print("  → output/sample_schemes.py (parsed data)")
    print("============================\n")


if __name__ == "__main__":
    main()
