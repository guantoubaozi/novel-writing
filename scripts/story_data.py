"""Canonical story-data loading, validation, and writing helpers."""

import json
import os
import re
import secrets
import stat
import tempfile
import copy
from pathlib import Path


DATA_FILES = {
    "timeline": Path("continuity/timeline.json"),
    "relationships": Path("continuity/relationships.json"),
    "clues": Path("continuity/clues.json"),
}

_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SOURCE_REF_PATTERN = re.compile(r"^ch-[a-z0-9]+(?:-[a-z0-9]+)*(?:#[^\s#]+)?$")
_CHAPTER_PATTERN = re.compile(r"^ch-[a-z0-9]+(?:-[a-z0-9]+)*$")
_CERTAINTIES = {"confirmed", "inferred", "author-planned"}
_VISIBILITIES = {"author", "spoiler-safe"}

_COLLECTIONS = (
    ("timeline", "events", "event-", (
        "id", "title", "story_time", "sequence", "chapter", "location",
        "participants", "summary", "causes", "effects", "kind", "certainty",
        "visibility", "source_refs",
    )),
    ("relationships", "characters", "char-", (
        "id", "name", "aliases", "role", "faction", "status", "first_chapter",
        "notes", "visibility", "source_refs",
    )),
    ("relationships", "relationships", "rel-", (
        "id", "source", "target", "type", "direction", "status", "start_chapter",
        "end_chapter", "description", "certainty", "visibility", "source_refs",
    )),
    ("clues", "mysteries", "mystery-", (
        "id", "title", "question", "status", "introduced_chapter", "resolved_chapter",
        "visibility", "source_refs",
    )),
    ("clues", "clues", "clue-", (
        "id", "title", "description", "status", "introduced_chapter", "known_by",
        "planned_payoff", "actual_payoff", "certainty", "visibility", "source_refs",
    )),
    ("clues", "links", "link-", (
        "id", "source", "target", "type", "certainty", "visibility", "source_refs",
    )),
)

_READER_ID_PREFIXES = {
    ("timeline", "events"): "event-reader-",
    ("relationships", "characters"): "char-reader-",
    ("relationships", "relationships"): "rel-reader-",
    ("clues", "mysteries"): "mystery-reader-",
    ("clues", "clues"): "clue-reader-",
    ("clues", "links"): "link-reader-",
}

_CHAPTER_FIELDS = {
    ("timeline", "events"): ("chapter",),
    ("relationships", "characters"): ("first_chapter",),
    ("relationships", "relationships"): ("start_chapter", "end_chapter"),
    ("clues", "mysteries"): ("introduced_chapter", "resolved_chapter"),
    ("clues", "clues"): ("introduced_chapter",),
    ("clues", "links"): (),
}

_TEXT_FIELDS = {
    ("timeline", "events"): (
        "title", "story_time", "chapter", "location", "summary", "kind",
        "certainty", "visibility",
    ),
    ("relationships", "characters"): (
        "name", "role", "faction", "status", "first_chapter", "notes",
        "visibility",
    ),
    ("relationships", "relationships"): (
        "source", "target", "type", "direction", "status", "start_chapter",
        "end_chapter", "description", "certainty", "visibility",
    ),
    ("clues", "mysteries"): (
        "title", "question", "status", "introduced_chapter",
        "resolved_chapter", "visibility",
    ),
    ("clues", "clues"): (
        "title", "description", "status", "introduced_chapter",
        "planned_payoff", "actual_payoff", "certainty", "visibility",
    ),
    ("clues", "links"): (
        "source", "target", "type", "certainty", "visibility",
    ),
}

_STRING_LIST_FIELDS = {
    ("timeline", "events"): ("participants", "causes", "effects"),
    ("relationships", "characters"): ("aliases",),
    ("relationships", "relationships"): (),
    ("clues", "mysteries"): (),
    ("clues", "clues"): ("known_by",),
    ("clues", "links"): (),
}

_INTEGER_FIELDS = {
    ("timeline", "events"): ("sequence",),
    ("relationships", "characters"): (),
    ("relationships", "relationships"): (),
    ("clues", "mysteries"): (),
    ("clues", "clues"): (),
    ("clues", "links"): (),
}


def load_story_data(project_root: Path) -> dict[str, dict]:
    """Load the three canonical JSON files below *project_root* as UTF-8."""
    root_descriptor = None
    continuity_descriptor = None
    try:
        root_descriptor, continuity_descriptor, identity = _open_canonical_directory(
            project_root
        )
        loaded = {}
        for domain, relative_path in DATA_FILES.items():
            _verify_continuity_identity(root_descriptor, identity)
            loaded[domain] = json.loads(
                _read_regular_leaf(
                    continuity_descriptor,
                    relative_path.name,
                ).decode("utf-8")
            )
        _verify_continuity_identity(root_descriptor, identity)
        return loaded
    finally:
        if continuity_descriptor is not None:
            os.close(continuity_descriptor)
        if root_descriptor is not None:
            os.close(root_descriptor)


def _directory_flags():
    return (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )


def _identity(metadata):
    return metadata.st_dev, metadata.st_ino


def _open_canonical_directory(project_root):
    root_descriptor = None
    continuity_descriptor = None
    try:
        root_descriptor = os.open(str(Path(project_root)), _directory_flags())
        root_metadata = os.fstat(root_descriptor)
        if not stat.S_ISDIR(root_metadata.st_mode):
            raise OSError("Project root must be a real directory")
        continuity_metadata = os.stat(
            "continuity",
            dir_fd=root_descriptor,
            follow_symlinks=False,
        )
        if not stat.S_ISDIR(continuity_metadata.st_mode):
            raise OSError("Canonical continuity entry must be a real directory")
        continuity_descriptor = os.open(
            "continuity",
            _directory_flags(),
            dir_fd=root_descriptor,
        )
        opened_metadata = os.fstat(continuity_descriptor)
        if (
            not stat.S_ISDIR(opened_metadata.st_mode)
            or _identity(opened_metadata) != _identity(continuity_metadata)
        ):
            raise OSError("Canonical continuity directory changed while opening")
        return (
            root_descriptor,
            continuity_descriptor,
            _identity(opened_metadata),
        )
    except BaseException:
        if continuity_descriptor is not None:
            os.close(continuity_descriptor)
        if root_descriptor is not None:
            os.close(root_descriptor)
        raise


def _verify_continuity_identity(root_descriptor, expected_identity):
    try:
        metadata = os.stat(
            "continuity",
            dir_fd=root_descriptor,
            follow_symlinks=False,
        )
    except OSError as error:
        raise OSError("Canonical continuity directory changed") from error
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or _identity(metadata) != expected_identity
    ):
        raise OSError("Canonical continuity directory changed")


def _read_regular_leaf(directory_descriptor, filename):
    file_descriptor = None
    try:
        file_descriptor = os.open(
            filename,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_descriptor,
        )
        metadata = os.fstat(file_descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise OSError("Canonical file must be a regular file: %s" % filename)
        with os.fdopen(file_descriptor, "rb") as input_file:
            file_descriptor = None
            return input_file.read()
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)


def _reader_identifier_maps(data):
    identifier_map = {}
    for domain, collection, _prefix, _required in _COLLECTIONS:
        prefix = _READER_ID_PREFIXES[(domain, collection)]
        records = sorted(data[domain][collection], key=lambda record: record["id"])
        for index, record in enumerate(records, 1):
            identifier_map[record["id"]] = "%s%03d" % (prefix, index)

    chapters = sorted({
        record.get(field)
        for domain, collection, _prefix, _required in _COLLECTIONS
        for record in data[domain][collection]
        for field in _CHAPTER_FIELDS[(domain, collection)]
        if record.get(field)
    })
    chapter_map = {
        chapter: "chapter-reader-%03d" % index
        for index, chapter in enumerate(chapters, 1)
    }
    return identifier_map, chapter_map


def _reader_reference(identifier_map, value):
    return identifier_map[value] if value else ""


def _reader_chapter(chapter_map, value):
    return chapter_map[value] if value else ""


def _redact_reader_data(data):
    identifier_map, chapter_map = _reader_identifier_maps(data)

    events = [{
        "id": _reader_reference(identifier_map, record["id"]),
        "title": record["title"],
        "story_time": record["story_time"],
        "sequence": record["sequence"],
        "chapter": _reader_chapter(chapter_map, record["chapter"]),
        "location": record["location"],
        "participants": [
            _reader_reference(identifier_map, value)
            for value in record["participants"]
        ],
        "summary": record["summary"],
        "causes": [
            _reader_reference(identifier_map, value)
            for value in record["causes"]
        ],
        "effects": [
            _reader_reference(identifier_map, value)
            for value in record["effects"]
        ],
        "kind": record["kind"],
        "certainty": record["certainty"],
        "visibility": "spoiler-safe",
        "source_refs": [],
    } for record in data["timeline"]["events"]]

    characters = [{
        "id": _reader_reference(identifier_map, record["id"]),
        "name": record["name"],
        "aliases": [],
        "role": "",
        "faction": "",
        "status": record["status"],
        "first_chapter": _reader_chapter(chapter_map, record["first_chapter"]),
        "notes": "",
        "visibility": "spoiler-safe",
        "source_refs": [],
    } for record in data["relationships"]["characters"]]

    relationships = [{
        "id": _reader_reference(identifier_map, record["id"]),
        "source": _reader_reference(identifier_map, record["source"]),
        "target": _reader_reference(identifier_map, record["target"]),
        "type": record["type"],
        "direction": record["direction"],
        "status": record["status"],
        "start_chapter": _reader_chapter(chapter_map, record["start_chapter"]),
        "end_chapter": _reader_chapter(chapter_map, record["end_chapter"]),
        "description": record["description"],
        "certainty": record["certainty"],
        "visibility": "spoiler-safe",
        "source_refs": [],
    } for record in data["relationships"]["relationships"]]

    mysteries = [{
        "id": _reader_reference(identifier_map, record["id"]),
        "title": record["title"],
        "question": record["question"],
        "status": record["status"],
        "introduced_chapter": _reader_chapter(
            chapter_map, record["introduced_chapter"]
        ),
        "resolved_chapter": _reader_chapter(
            chapter_map, record["resolved_chapter"]
        ) if record["status"] == "resolved" else "",
        "visibility": "spoiler-safe",
        "source_refs": [],
    } for record in data["clues"]["mysteries"]]

    clues = [{
        "id": _reader_reference(identifier_map, record["id"]),
        "title": record["title"],
        "description": record["description"],
        "status": record["status"],
        "introduced_chapter": _reader_chapter(
            chapter_map, record["introduced_chapter"]
        ),
        "known_by": [
            _reader_reference(identifier_map, value)
            for value in record["known_by"]
        ],
        "planned_payoff": "",
        "actual_payoff": (
            record["actual_payoff"] if record["status"] == "resolved" else ""
        ),
        "certainty": record["certainty"],
        "visibility": "spoiler-safe",
        "source_refs": [],
    } for record in data["clues"]["clues"]]

    links = [{
        "id": _reader_reference(identifier_map, record["id"]),
        "source": _reader_reference(identifier_map, record["source"]),
        "target": _reader_reference(identifier_map, record["target"]),
        "type": record["type"],
        "certainty": record["certainty"],
        "visibility": "spoiler-safe",
        "source_refs": [],
    } for record in data["clues"]["links"]]

    return {
        "timeline": {"schema_version": data["timeline"]["schema_version"], "events": events},
        "relationships": {
            "schema_version": data["relationships"]["schema_version"],
            "characters": characters,
            "relationships": relationships,
        },
        "clues": {
            "schema_version": data["clues"]["schema_version"],
            "mysteries": mysteries,
            "clues": clues,
            "links": links,
        },
    }


def filter_visibility(data: dict[str, dict], mode: str) -> dict[str, dict]:
    """Return story data suitable for an author or reader dashboard."""
    if mode not in {"author", "reader"}:
        raise ValueError("Unknown dashboard mode: %s" % mode)
    errors = validate_story_data(data)
    if errors:
        raise _validation_error("Invalid story data:", errors)
    filtered = copy.deepcopy(data)
    if mode == "author":
        return filtered

    for domain, collection, _prefix, _required in _COLLECTIONS:
        records = filtered.get(domain, {}).get(collection, [])
        filtered[domain][collection] = [
            record
            for record in records
            if record.get("visibility") == "spoiler-safe"
            and record.get("certainty") != "author-planned"
        ]

    character_ids = {
        record["id"]
        for record in filtered["relationships"]["characters"]
    }
    filtered["relationships"]["relationships"] = [
        record
        for record in filtered["relationships"]["relationships"]
        if record.get("source") in character_ids
        and record.get("target") in character_ids
    ]
    retained_ids = {
        record["id"]
        for domain, collection, _prefix, _required in _COLLECTIONS
        if (domain, collection) != ("clues", "links")
        for record in filtered[domain][collection]
    }
    filtered["clues"]["links"] = [
        record
        for record in filtered["clues"]["links"]
        if record.get("source") in retained_ids
        and record.get("target") in retained_ids
    ]
    retained_ids.update(
        record["id"] for record in filtered["clues"]["links"]
    )

    for event in filtered["timeline"]["events"]:
        event["participants"] = [
            character_id
            for character_id in event.get("participants", [])
            if character_id in character_ids
        ]
        for field in ("causes", "effects"):
            event[field] = [
                record_id
                for record_id in event.get(field, [])
                if record_id in retained_ids
            ]

    for clue in filtered["clues"]["clues"]:
        clue["known_by"] = [
            character_id
            for character_id in clue.get("known_by", [])
            if character_id in character_ids
        ]
    return _redact_reader_data(filtered)


def atomic_write_json(path: Path, value: object) -> None:
    """Atomically publish one canonical, human-readable JSON file."""
    path = Path(path)
    file_descriptor = None
    temporary_path = None
    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=".%s." % path.name, suffix=".tmp", dir=str(path.parent)
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as output:
            file_descriptor = None
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(str(temporary_path), str(path))
        temporary_path = None
    except Exception:
        if file_descriptor is not None:
            os.close(file_descriptor)
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
        raise


def _create_exclusive_file(directory_descriptor, target_name, suffix):
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
    )
    for _attempt in range(100):
        filename = ".%s.%s%s" % (
            target_name,
            secrets.token_hex(8),
            suffix,
        )
        try:
            descriptor = os.open(
                filename,
                flags,
                0o600,
                dir_fd=directory_descriptor,
            )
            return descriptor, filename
        except FileExistsError:
            continue
    raise FileExistsError("Unable to allocate canonical temporary file")


def _unlink_relative(directory_descriptor, filename):
    if filename is None:
        return
    try:
        os.unlink(filename, dir_fd=directory_descriptor)
    except FileNotFoundError:
        pass


def _write_json_temporary(directory_descriptor, target_name, value):
    file_descriptor = None
    temporary_name = None
    try:
        file_descriptor, temporary_name = _create_exclusive_file(
            directory_descriptor,
            target_name,
            ".tmp",
        )
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as output:
            file_descriptor = None
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        return temporary_name
    except BaseException:
        if file_descriptor is not None:
            os.close(file_descriptor)
        _unlink_relative(directory_descriptor, temporary_name)
        raise


def _backup_file(directory_descriptor, target_name):
    file_descriptor = None
    backup_name = None
    try:
        original_bytes = _read_regular_leaf(directory_descriptor, target_name)
        file_descriptor, backup_name = _create_exclusive_file(
            directory_descriptor,
            target_name,
            ".bak",
        )
        with os.fdopen(file_descriptor, "wb") as output:
            file_descriptor = None
            output.write(original_bytes)
            output.flush()
            os.fsync(output.fileno())
        return backup_name
    except BaseException:
        if file_descriptor is not None:
            os.close(file_descriptor)
        _unlink_relative(directory_descriptor, backup_name)
        raise


def _validation_error(prefix: str, errors: list[str]) -> ValueError:
    return ValueError(prefix + "\n" + "\n".join(errors))


def write_story_data_atomic(project_root: Path, data: dict[str, dict]) -> None:
    """Validate and atomically publish all canonical story-data files."""
    errors = validate_story_data(data)
    if errors:
        raise _validation_error("Invalid story data:", errors)

    root = Path(project_root)
    targets = {
        domain: relative_path.name
        for domain, relative_path in DATA_FILES.items()
    }
    temporary_paths = {}
    backup_paths = {}
    preserved_backup_paths = set()
    root_descriptor = None
    continuity_descriptor = None
    try:
        root_descriptor, continuity_descriptor, identity = _open_canonical_directory(
            root
        )
        for target in targets.values():
            _read_regular_leaf(continuity_descriptor, target)
        _verify_continuity_identity(root_descriptor, identity)

        for domain, target in targets.items():
            temporary_paths[domain] = _write_json_temporary(
                continuity_descriptor,
                target,
                data[domain],
            )
        for domain, target in targets.items():
            backup_paths[domain] = _backup_file(
                continuity_descriptor,
                target,
            )

        try:
            for domain, target in targets.items():
                _verify_continuity_identity(root_descriptor, identity)
                os.replace(
                    temporary_paths[domain],
                    target,
                    src_dir_fd=continuity_descriptor,
                    dst_dir_fd=continuity_descriptor,
                )
                temporary_paths[domain] = None
                _verify_continuity_identity(root_descriptor, identity)
        except BaseException as publish_error:
            restore_errors = []
            for domain, target in targets.items():
                backup_path = backup_paths[domain]
                try:
                    os.replace(
                        backup_path,
                        target,
                        src_dir_fd=continuity_descriptor,
                        dst_dir_fd=continuity_descriptor,
                    )
                    backup_paths[domain] = None
                except BaseException as restore_error:
                    preserved_backup_paths.add(backup_path)
                    restore_errors.append(
                        "%s restore failed: %s; original backup preserved at %s"
                        % (
                            domain,
                            restore_error,
                            root / "continuity" / backup_path,
                        )
                    )
            os.fsync(continuity_descriptor)
            if restore_errors:
                raise RuntimeError(
                    "Failed to restore story data after publish error %r: %s"
                    % (publish_error, "; ".join(restore_errors))
                ) from publish_error
            raise

        os.fsync(continuity_descriptor)
        for domain, backup_path in backup_paths.items():
            _unlink_relative(continuity_descriptor, backup_path)
            backup_paths[domain] = None
    finally:
        for path in list(temporary_paths.values()) + list(backup_paths.values()):
            if path is not None and path not in preserved_backup_paths:
                if continuity_descriptor is not None:
                    _unlink_relative(continuity_descriptor, path)
        if continuity_descriptor is not None:
            os.close(continuity_descriptor)
        if root_descriptor is not None:
            os.close(root_descriptor)


def _record_id(record, fallback):
    if isinstance(record, dict) and isinstance(record.get("id"), str):
        return record["id"]
    return fallback


def _validate_references(errors, record_id, record):
    references = record.get("source_refs")
    if not isinstance(references, list):
        errors.append("%s.source_refs must be a list of strings" % record_id)
        return
    for reference in references:
        if not isinstance(reference, str) or not _SOURCE_REF_PATTERN.fullmatch(reference):
            errors.append("%s.source_refs has invalid reference %r" % (record_id, reference))


def _validate_record(errors, record, fallback, prefix, required_fields):
    if not isinstance(record, dict):
        errors.append("%s must be an object" % fallback)
        return None
    record_id = _record_id(record, fallback)
    for field in required_fields:
        if field not in record:
            errors.append("%s missing required field %s" % (record_id, field))
    for field in sorted(record, key=lambda value: str(value)):
        if field not in required_fields:
            errors.append("%s.%s is not a canonical field" % (record_id, field))
    identifier = record.get("id")
    if not isinstance(identifier, str) or not identifier.startswith(prefix) or not _ID_PATTERN.fullmatch(identifier):
        errors.append("%s.id must use prefix %s and lowercase ASCII hyphens" % (record_id, prefix))
    _validate_references(errors, record_id, record)
    return record_id


def _validate_field_types(errors, record_id, record, domain, collection):
    key = domain, collection
    for field in _TEXT_FIELDS[key]:
        if field in record and not isinstance(record[field], str):
            errors.append("%s.%s must be a string" % (record_id, field))
    for field in _STRING_LIST_FIELDS[key]:
        if field not in record:
            continue
        value = record[field]
        if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value
        ):
            errors.append("%s.%s must be a list of strings" % (record_id, field))
    for field in _INTEGER_FIELDS[key]:
        if field in record and (
            not isinstance(record[field], int) or isinstance(record[field], bool)
        ):
            errors.append("%s.%s must be an integer" % (record_id, field))
    for field in _CHAPTER_FIELDS[key]:
        value = record.get(field)
        if isinstance(value, str) and value and not _CHAPTER_PATTERN.fullmatch(value):
            errors.append(
                "%s.%s must be empty or a valid chapter id" % (record_id, field)
            )


def _validate_enum(errors, record_id, record, field, allowed):
    value = record.get(field)
    if not isinstance(value, str) or value not in allowed:
        errors.append("%s.%s has invalid value %r" % (record_id, field, value))


def _validate_character_references(errors, record_id, values, field, character_ids):
    if not isinstance(values, list):
        return
    for character_id in values:
        if isinstance(character_id, str) and character_id not in character_ids:
            errors.append("%s.%s unknown character %s" % (record_id, field, character_id))


def validate_story_data(data: dict[str, dict]) -> list[str]:
    """Return every schema and cross-reference error in deterministic order."""
    errors = []
    if not isinstance(data, dict):
        return ["story data must be an object"]

    domains = {}
    for domain in ("timeline", "relationships", "clues"):
        domain_value = data.get(domain)
        if not isinstance(domain_value, dict):
            errors.append("%s must be an object" % domain)
            domains[domain] = {}
            continue
        domains[domain] = domain_value
        schema_version = domain_value.get("schema_version")
        if (
            not isinstance(schema_version, int)
            or isinstance(schema_version, bool)
            or schema_version != 1
        ):
            errors.append("%s.schema_version must be 1" % domain)

    collections = {}
    for domain, collection, _prefix, _required in _COLLECTIONS:
        entries = domains[domain].get(collection)
        if not isinstance(entries, list):
            errors.append("%s.%s must be a list" % (domain, collection))
            entries = []
        collections[(domain, collection)] = entries

    identifiers = {}
    for domain, collection, prefix, required_fields in _COLLECTIONS:
        seen = set()
        for index, record in enumerate(collections[(domain, collection)]):
            fallback = "%s.%s[%d]" % (domain, collection, index)
            record_id = _validate_record(errors, record, fallback, prefix, required_fields)
            if record_id is None:
                continue
            if record_id in seen:
                errors.append("duplicate id %s" % record_id)
            seen.add(record_id)
            identifiers.setdefault((domain, collection), set()).add(record_id)

            if isinstance(record, dict):
                _validate_field_types(
                    errors,
                    record_id,
                    record,
                    domain,
                    collection,
                )
                if "certainty" in required_fields:
                    _validate_enum(errors, record_id, record, "certainty", _CERTAINTIES)
                if "visibility" in required_fields:
                    _validate_enum(errors, record_id, record, "visibility", _VISIBILITIES)
                if (domain, collection) == ("timeline", "events"):
                    _validate_enum(errors, record_id, record, "kind", {"present", "flashback", "flashforward", "parallel", "reported"})
                elif (domain, collection) == ("relationships", "characters"):
                    _validate_enum(errors, record_id, record, "status", {"planned", "active", "absent", "missing", "dead", "unknown"})
                elif (domain, collection) == ("relationships", "relationships"):
                    _validate_enum(errors, record_id, record, "direction", {"directed", "mutual"})
                    _validate_enum(errors, record_id, record, "status", {"planned", "active", "strained", "hidden", "ended"})
                elif (domain, collection) == ("clues", "mysteries"):
                    _validate_enum(errors, record_id, record, "status", {"open", "partially-resolved", "resolved"})
                elif (domain, collection) == ("clues", "clues"):
                    _validate_enum(errors, record_id, record, "status", {"planned", "seeded", "noticed", "interpreted", "confirmed", "misleading", "disproved", "resolved"})
                elif (domain, collection) == ("clues", "links"):
                    _validate_enum(errors, record_id, record, "type", {"supports", "contradicts", "misleads", "reveals", "possessed-by", "points-to"})

    canonical_record_ids = set().union(
        *(
            identifiers.get((domain, collection), set())
            for domain, collection, _prefix, _required in _COLLECTIONS
        )
    )
    for record in collections[("timeline", "events")]:
        if isinstance(record, dict):
            record_id = _record_id(record, "timeline event")
            for field in ("causes", "effects"):
                references = record.get(field)
                if not isinstance(references, list):
                    continue
                for reference in references:
                    if not isinstance(reference, str):
                        continue
                    if not reference:
                        errors.append(
                            "%s.%s must contain non-empty canonical record ids"
                            % (record_id, field)
                        )
                    elif reference not in canonical_record_ids:
                        errors.append(
                            "%s.%s unknown canonical record %s"
                            % (record_id, field, reference)
                        )

    character_ids = identifiers.get(("relationships", "characters"), set())
    for record in collections[("timeline", "events")]:
        if isinstance(record, dict):
            _validate_character_references(errors, _record_id(record, "timeline event"), record.get("participants"), "participants", character_ids)
    for record in collections[("relationships", "relationships")]:
        if isinstance(record, dict):
            record_id = _record_id(record, "relationship")
            for field in ("source", "target"):
                character_id = record.get(field)
                if isinstance(character_id, str) and character_id not in character_ids:
                    errors.append("%s.%s unknown character %s" % (record_id, field, character_id))
    for record in collections[("clues", "clues")]:
        if isinstance(record, dict):
            _validate_character_references(errors, _record_id(record, "clue"), record.get("known_by"), "known_by", character_ids)

    linkable_collections = (
        ("timeline", "events"),
        ("relationships", "characters"),
        ("relationships", "relationships"),
        ("clues", "mysteries"),
        ("clues", "clues"),
    )
    linkable_ids = set().union(
        *(identifiers.get(collection, set()) for collection in linkable_collections)
    )
    for record in collections[("clues", "links")]:
        if isinstance(record, dict):
            record_id = _record_id(record, "clue link")
            for field in ("source", "target"):
                target_id = record.get(field)
                if isinstance(target_id, str) and target_id not in linkable_ids:
                    errors.append("%s.%s unknown endpoint %s" % (record_id, field, target_id))
    return errors
