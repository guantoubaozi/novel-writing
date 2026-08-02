"""Render the canonical novel data as one offline HTML dashboard."""

import argparse
import copy
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import secrets
import sys

try:
    from scripts.story_data import filter_visibility, load_story_data, validate_story_data
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.story_data import filter_visibility, load_story_data, validate_story_data


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = SKILL_ROOT / "assets" / "dashboard-template.html"
VIEW_TYPES = ("timeline", "relationships", "clues")


def json_for_html(value: object) -> str:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_dashboard(
    project_root: Path,
    output_path: Path,
    mode: str = "author",
    types=None,
) -> Path:
    return _render_dashboard(
        project_root,
        output_path,
        mode,
        types=types,
        allow_outside=False,
    )


def _normalize_types(types):
    if types is None:
        return VIEW_TYPES
    values = types.split(",") if isinstance(types, str) else list(types)
    if not values or values == [""]:
        raise ValueError("Select at least one dashboard type")
    normalized = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Dashboard types must not contain empty values")
        normalized.append(value.strip())
    duplicates = sorted({value for value in normalized if normalized.count(value) > 1})
    if duplicates:
        raise ValueError("duplicate dashboard type: %s" % duplicates[0])
    unknown = sorted(set(normalized) - set(VIEW_TYPES))
    if unknown:
        raise ValueError("unknown dashboard type: %s" % unknown[0])
    return tuple(view_type for view_type in VIEW_TYPES if view_type in normalized)


def _select_story_views(story, enabled_views):
    collections = (
        ("timeline", "events"),
        ("relationships", "characters"),
        ("relationships", "relationships"),
        ("clues", "mysteries"),
        ("clues", "clues"),
        ("clues", "links"),
    )
    view_collections = {
        "timeline": (("timeline", "events"),),
        "relationships": (
            ("relationships", "characters"),
            ("relationships", "relationships"),
        ),
        "clues": (
            ("clues", "mysteries"),
            ("clues", "clues"),
            ("clues", "links"),
        ),
    }
    reference_fields = {
        ("timeline", "events"): ("participants", "causes", "effects"),
        ("relationships", "characters"): (),
        ("relationships", "relationships"): ("source", "target"),
        ("clues", "mysteries"): (),
        ("clues", "clues"): ("known_by",),
        ("clues", "links"): ("source", "target"),
    }
    record_index = {
        record["id"]: (domain, collection, record)
        for domain, collection in collections
        for record in story[domain][collection]
    }
    pending = [
        record["id"]
        for view_type in enabled_views
        for domain, collection in view_collections[view_type]
        for record in story[domain][collection]
    ]
    retained_ids = set()
    while pending:
        record_id = pending.pop()
        if record_id in retained_ids:
            continue
        if record_id not in record_index:
            raise ValueError("unknown dependency id %s" % record_id)
        domain, collection, record = record_index[record_id]
        retained_ids.add(record_id)
        for field in reference_fields[(domain, collection)]:
            value = record[field]
            references = value if isinstance(value, list) else (value,)
            pending.extend(
                reference
                for reference in references
                if reference not in retained_ids
            )

    selected = {
        "timeline": {
            "schema_version": story["timeline"]["schema_version"],
            "events": [],
        },
        "relationships": {
            "schema_version": story["relationships"]["schema_version"],
            "characters": [],
            "relationships": [],
        },
        "clues": {
            "schema_version": story["clues"]["schema_version"],
            "mysteries": [],
            "clues": [],
            "links": [],
        },
    }
    for domain, collection in collections:
        selected[domain][collection] = [
            copy.deepcopy(record)
            for record in story[domain][collection]
            if record["id"] in retained_ids
        ]
    return selected


def _generated_at(project_root: Path) -> str:
    inputs = [project_root / "novel.json"] + [
        project_root / "continuity" / filename
        for filename in ("timeline.json", "relationships.json", "clues.json")
    ]
    timestamp = max(path.stat().st_mtime for path in inputs)
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _safe_output_path(
    project_root: Path,
    output_path: Path,
    allow_outside: bool,
):
    project_root = Path(project_root).resolve(strict=True)
    visualizations = project_root / "visualizations"
    if visualizations.is_symlink():
        raise ValueError("Refusing symlink visualization directory: %s" % visualizations)
    visualization_root = visualizations.resolve(strict=True)

    output_path = Path(output_path).expanduser()
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path
    if output_path.is_symlink():
        raise ValueError("Refusing symlink dashboard output: %s" % output_path)
    current = Path(output_path.anchor)
    for component in output_path.parent.parts[1:]:
        current = current / component
        if current.is_symlink():
            raise ValueError("Refusing symlink output parent: %s" % current)
    parent = output_path.parent.resolve(strict=True)
    resolved = parent / output_path.name
    if not allow_outside:
        try:
            resolved.relative_to(visualization_root)
        except ValueError:
            raise ValueError(
                "Dashboard output must stay inside %s" % visualization_root
            )
    parent_stat = os.stat(str(parent), follow_symlinks=False)
    return resolved, (parent_stat.st_dev, parent_stat.st_ino)


def _atomic_write_text(path: Path, value: str, expected_directory) -> None:
    directory_descriptor = None
    file_descriptor = None
    temporary_name = None
    try:
        directory_flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        directory_descriptor = os.open(str(path.parent), directory_flags)
        directory_stat = os.fstat(directory_descriptor)
        actual_directory = (directory_stat.st_dev, directory_stat.st_ino)
        if actual_directory != expected_directory:
            raise OSError("Dashboard output directory changed before publication")

        file_flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
        )
        for _attempt in range(100):
            candidate = ".%s.%s.tmp" % (path.name, secrets.token_hex(8))
            try:
                file_descriptor = os.open(
                    candidate,
                    file_flags,
                    0o600,
                    dir_fd=directory_descriptor,
                )
                temporary_name = candidate
                break
            except FileExistsError:
                continue
        if file_descriptor is None:
            raise FileExistsError("Unable to allocate dashboard temporary file")

        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as output:
            file_descriptor = None
            output.write(value)
            output.flush()
            os.fsync(output.fileno())
        os.replace(
            temporary_name,
            path.name,
            src_dir_fd=directory_descriptor,
            dst_dir_fd=directory_descriptor,
        )
        temporary_name = None
        os.fsync(directory_descriptor)
    except BaseException:
        if file_descriptor is not None:
            os.close(file_descriptor)
        raise
    finally:
        if temporary_name is not None and directory_descriptor is not None:
            try:
                os.unlink(temporary_name, dir_fd=directory_descriptor)
            except FileNotFoundError:
                pass
        if directory_descriptor is not None:
            os.close(directory_descriptor)


def _interpolate_template(template: str, replacements) -> str:
    positioned = []
    for token, value in replacements.items():
        if template.count(token) != 1:
            raise ValueError("Dashboard template must contain %s exactly once" % token)
        positioned.append((template.index(token), token, value))

    chunks = []
    cursor = 0
    for position, token, value in sorted(positioned):
        chunks.append(template[cursor:position])
        chunks.append(value)
        cursor = position + len(token)
    chunks.append(template[cursor:])
    return "".join(chunks)


def _render_dashboard(
    project_root: Path,
    output_path: Path,
    mode: str,
    types,
    allow_outside: bool,
) -> Path:
    enabled_views = _normalize_types(types)
    project_root = Path(project_root).resolve(strict=True)
    output_path, expected_directory = _safe_output_path(
        project_root, output_path, allow_outside
    )

    story_data = load_story_data(project_root)
    errors = validate_story_data(story_data)
    if errors:
        raise ValueError("Invalid story data:\n" + "\n".join(errors))
    filtered = _select_story_views(
        filter_visibility(story_data, mode),
        enabled_views,
    )

    config_path = project_root / "novel.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    title = config.get("title")
    if not isinstance(title, str):
        raise ValueError("novel.json title must be a string")
    language = config.get("language", "und")
    if not isinstance(language, str):
        raise ValueError("novel.json language must be a string")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    generated_at = _generated_at(project_root)
    if mode == "reader":
        generated_at = generated_at.split("T", 1)[0]
    payload = {
        "enabled_views": list(enabled_views),
        "generated_at": generated_at,
        "language": language,
        "mode": mode,
        "story": filtered,
        "title": title,
    }
    rendered = _interpolate_template(
        template,
        {
            "__NOVEL_TITLE__": html.escape(title),
            "__STORY_DATA__": json_for_html(payload),
        },
    )
    _atomic_write_text(output_path, rendered, expected_directory)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render an offline novel dashboard."
    )
    parser.add_argument("project_dir", metavar="PROJECT_DIR", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--mode", choices=("author", "reader"), default="author")
    parser.add_argument(
        "--types",
        help="comma-separated selection: timeline,relationships,clues",
    )
    arguments = parser.parse_args()

    try:
        project_root = arguments.project_dir.resolve(strict=True)
        if arguments.output is None:
            filename = (
                "novel-dashboard.html"
                if arguments.mode == "author"
                else "reader-dashboard.html"
            )
            output_path = project_root / "visualizations" / filename
            allow_outside = False
        else:
            output_path = arguments.output
            allow_outside = True
        rendered = _render_dashboard(
            project_root,
            output_path,
            arguments.mode,
            types=arguments.types,
            allow_outside=allow_outside,
        )
    except Exception as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return 1

    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
