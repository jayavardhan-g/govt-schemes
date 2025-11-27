import sys
import os
from importlib import import_module

script_folder = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_folder)

def fetch_all():
    print("fetching HTML")
    try:
        fetcher = import_module("fetcher")
    except Exception as e:
        print("Error: Could not import fetcher.py")
        print(e)
        sys.exit(1)

    fetcher.main()
    print("fetching completed.\n")


def parser_start():
    print("p arsing HTML")
    parser = import_module("parser")

    parser.parse_all_html()
    print("Parsing completed")


def main():
    fetch_all()
    parser_start()

if __name__ == "__main__":
    main()
