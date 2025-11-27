import sys
import os
from importlib import import_module

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

def run_fetcher():
    print("fetching HTML")
    try:
        fetcher = import_module("fetcher")
    except Exception as e:
        print("Error: Could not import fetcher.py")
        print(e)
        sys.exit(1)

    fetcher.main()
    print("fetching completed.\n")


def run_parser():
    print("p arsing HTML")
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

if __name__ == "__main__":
    main()
