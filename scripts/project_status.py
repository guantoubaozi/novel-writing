"""Report compact, deterministic progress metrics for a novel project."""

import argparse
import json
import sys
from pathlib import Path

try:
    from scripts.story_data import load_story_data
except ModuleNotFoundError:
    from story_data import load_story_data


_CANONICAL_COLLECTIONS = (
    ("timeline", "events"),
    ("relationships", "characters"),
    ("relationships", "relationships"),
    ("clues", "mysteries"),
    ("clues", "clues"),
    ("clues", "links"),
)


def _is_contained(path: Path, directory: Path) -> bool:
    resolved_path = path.resolve()
    resolved_directory = directory.resolve()
    return resolved_path == resolved_directory or resolved_directory in resolved_path.parents


def _safe_directory(project_root: Path, name: str):
    directory = project_root / name
    if not directory.is_dir() or not _is_contained(directory, project_root):
        return None
    return directory


def _is_cjk(character: str) -> bool:
    codepoint = ord(character)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x2EE5F
        or 0x2F800 <= codepoint <= 0x2FA1F
        or 0x30000 <= codepoint <= 0x323AF
    )


def count_text_units(text: str) -> int:
    count = 0
    in_token = False
    for character in text:
        if _is_cjk(character):
            count += 1
            in_token = False
        elif character.isalnum():
            if not in_token:
                count += 1
                in_token = True
        else:
            in_token = False
    return count


def load_canonical_collections(project_root: Path) -> dict:
    data = load_story_data(project_root)
    collections = {}
    for domain, collection in _CANONICAL_COLLECTIONS:
        document = data.get(domain)
        if not isinstance(document, dict):
            raise ValueError(domain + " must be an object")
        if document.get("schema_version") != 1:
            raise ValueError(domain + ".schema_version must be 1")
        entries = document.get(collection)
        if not isinstance(entries, list):
            raise ValueError(domain + "." + collection + " must be a list")
        collections[(domain, collection)] = entries
    return collections


_STATUS_KEYS = (
    "chapters", "text_units", "open_mysteries", "unresolved_clues", "active_relationships",
)


def build_status(project_root: Path) -> dict:
    project_root = Path(project_root)
    novel_path = project_root / "novel.json"
    try:
        config = json.loads(novel_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError("missing required novel.json") from error
    except json.JSONDecodeError as error:
        raise ValueError("invalid JSON in novel.json: " + error.msg) from error
    if not isinstance(config, dict):
        raise ValueError("novel.json must contain a JSON object")
    chapters_dir = _safe_directory(project_root, "chapters")
    chapters = [] if chapters_dir is None else sorted(
        path for path in chapters_dir.iterdir()
        if path.is_file() and path.suffix.lower() == ".md" and path.name.lower() != "index.md"
        and _is_contained(path, chapters_dir)
    )
    text_units = sum(count_text_units(path.read_text(encoding="utf-8")) for path in chapters)
    collections = load_canonical_collections(project_root)
    mysteries = collections[("clues", "mysteries")]
    clues = collections[("clues", "clues")]
    relationships = collections[("relationships", "relationships")]
    return {
        "chapters": len(chapters),
        "text_units": text_units,
        "open_mysteries": sum(item.get("status") == "open" for item in mysteries if isinstance(item, dict)),
        "unresolved_clues": sum(item.get("status") != "resolved" for item in clues if isinstance(item, dict)),
        "active_relationships": sum(item.get("status") == "active" for item in relationships if isinstance(item, dict)),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Show novel project status.")
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        status = build_status(args.project_dir)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.format == "json":
        sys.stdout.write(json.dumps(status, ensure_ascii=False, sort_keys=True) + "\n")
    else:
        for key in _STATUS_KEYS:
            sys.stdout.write("{}: {}\n".format(key, status[key]))
    return 0


if __name__ == "__main__":
    main()
