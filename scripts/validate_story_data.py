"""Command-line validation for a novel project's canonical story data."""

import json
import sys
from pathlib import Path

try:
    from scripts.story_data import load_story_data, validate_story_data
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.story_data import load_story_data, validate_story_data


def main(arguments):
    if len(arguments) != 1:
        print("Usage: python3 scripts/validate_story_data.py PROJECT_DIR", file=sys.stderr)
        return 2
    try:
        data = load_story_data(Path(arguments[0]))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return 2
    errors = validate_story_data(data)
    if errors:
        for error in errors:
            print("ERROR: %s" % error)
        return 1
    print("Story data is valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
