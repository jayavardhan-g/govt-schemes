#!/usr/bin/env python3
import sys
import os
from importlib import import_module

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

def run_fetcher():
    print("\n============================")
    print(" STEP 1: Fetching HTML")
    print("============================")
    try:
        fetcher = import_module("fetcher")
    except Exception as e:
        print("Error: Could not import fetcher.py")
        print(e)
        sys.exit(1)

    fetcher.main()
    print("Fetching completed.\n")


def run_parser():
    print("\n============================")
    print(" STEP 2: Parsing HTML")
    print("============================")
    try:
        parser = import_module("parser")
    except Exception as e:
        print("Error: Could not import parser.py")
        print(e)
        sys.exit(1)

    parser.parse_all_html()
    print("Parsing completed.\n")


def main():
    run_fetcher()
    run_parser()
    print("\n============================")
    print("  DONE! Check:")
    print("  → output/raw_html/ (raw HTML files)")
    print("  → output/sample_schemes.py (final parsed output)")
    print("============================\n")


if __name__ == "__main__":
    main()
