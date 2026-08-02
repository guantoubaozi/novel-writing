"""Merge a complete chapter update packet into canonical story data."""

import argparse
import copy
import hashlib
import hmac
import json
import re
import sys
from pathlib import Path
from typing import Optional

try:
    from scripts.story_data import (
        load_story_data,
        validate_story_data,
        write_story_data_atomic,
    )
except ImportError:
    from story_data import load_story_data, validate_story_data, write_story_data_atomic


_CHAPTER_PATTERN = re.compile(r"^ch-[a-z0-9]+(?:-[a-z0-9]+)*$")
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_PACKET_COLLECTIONS = (
    ("timeline_events", "timeline", "events"),
    ("characters", "relationships", "characters"),
    ("relationships", "relationships", "relationships"),
    ("mysteries", "clues", "mysteries"),
    ("clues", "clues", "clues"),
    ("clue_links", "clues", "links"),
)


def upsert_records(
    existing: list[dict], incoming: list[dict]
) -> tuple[list[dict], int, int]:
    """Return deep-copied records with incoming IDs replaced or appended."""
    positions = {record["id"]: index for index, record in enumerate(existing)}
    result = [copy.deepcopy(record) for record in existing]
    added = 0
    updated = 0
    for record in incoming:
        record_copy = copy.deepcopy(record)
        if record_copy["id"] in positions:
            result[positions[record_copy["id"]]] = record_copy
            updated += 1
        else:
            positions[record_copy["id"]] = len(result)
            result.append(record_copy)
            added += 1
    return result, added, updated


def _validate_packet(packet: dict) -> None:
    if not isinstance(packet, dict):
        raise ValueError("update packet must be an object")
    if "chapter" not in packet:
        raise ValueError("update packet missing required key chapter")
    chapter = packet["chapter"]
    if not isinstance(chapter, str) or not _CHAPTER_PATTERN.fullmatch(chapter):
        raise ValueError("update packet chapter must be a valid chapter id")

    for packet_key, _domain, _collection in _PACKET_COLLECTIONS:
        if packet_key not in packet:
            raise ValueError("update packet missing required key %s" % packet_key)
        records = packet[packet_key]
        if not isinstance(records, list):
            raise ValueError("update packet %s must be a list" % packet_key)
        for index, record in enumerate(records):
            if not isinstance(record, dict) or not isinstance(record.get("id"), str):
                raise ValueError(
                    "update packet %s[%d] must contain a string id"
                    % (packet_key, index)
                )


def merge_update_packet(
    data: dict[str, dict], packet: dict
) -> tuple[dict[str, dict], dict[str, int]]:
    """Upsert a validated update packet into a copied in-memory state."""
    _validate_packet(packet)
    merged = copy.deepcopy(data)
    summary = {}
    for packet_key, domain, collection in _PACKET_COLLECTIONS:
        try:
            existing = merged[domain][collection]
        except (KeyError, TypeError):
            errors = validate_story_data(merged)
            raise ValueError(
                "Invalid merged story data:\n" + "\n".join(errors)
            )
        if not isinstance(existing, list) or any(
            not isinstance(record, dict) or not isinstance(record.get("id"), str)
            for record in existing
        ):
            errors = validate_story_data(merged)
            raise ValueError(
                "Invalid merged story data:\n" + "\n".join(errors)
            )
        records, added, updated = upsert_records(
            existing, packet[packet_key]
        )
        merged[domain][collection] = records
        summary[collection + "_added"] = added
        summary[collection + "_updated"] = updated

    errors = validate_story_data(merged)
    if errors:
        raise ValueError("Invalid merged story data:\n" + "\n".join(errors))
    return merged, summary


def read_verified_packet(
    update_file: Path, expected_sha256: Optional[str] = None
) -> dict:
    """Read once, optionally verify, and parse those same bytes."""
    packet_bytes = update_file.read_bytes()
    if expected_sha256 is not None:
        if not _SHA256_PATTERN.fullmatch(expected_sha256):
            raise ValueError(
                "expected SHA-256 must be exactly 64 hexadecimal characters"
            )
        actual_sha256 = hashlib.sha256(packet_bytes).hexdigest()
        normalized_expected = expected_sha256.lower()
        if not hmac.compare_digest(actual_sha256, normalized_expected):
            raise ValueError(
                "update packet SHA-256 mismatch: expected %s, got %s"
                % (normalized_expected, actual_sha256)
            )
    return json.loads(packet_bytes)


def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(
        description="Merge a chapter update packet into canonical story data."
    )
    parser.add_argument("project_dir", metavar="PROJECT_DIR", type=Path)
    parser.add_argument("update_file", metavar="UPDATE_FILE", type=Path)
    parser.add_argument("--expected-sha256", metavar="HEX")
    parser.add_argument("--dry-run", action="store_true")
    parsed = parser.parse_args(arguments)

    try:
        packet = read_verified_packet(
            parsed.update_file,
            parsed.expected_sha256,
        )
        data = load_story_data(parsed.project_dir)
        merged, summary = merge_update_packet(data, packet)
        if not parsed.dry_run:
            write_story_data_atomic(parsed.project_dir, merged)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return 1

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
