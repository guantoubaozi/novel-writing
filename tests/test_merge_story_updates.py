import ast
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.merge_story_updates import (
    merge_update_packet,
    read_verified_packet,
    upsert_records,
)
from scripts.story_data import DATA_FILES, validate_story_data, write_story_data_atomic


ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "chapter-001-update.json"


def empty_data():
    return {
        "timeline": {"schema_version": 1, "events": []},
        "relationships": {
            "schema_version": 1,
            "characters": [],
            "relationships": [],
        },
        "clues": {
            "schema_version": 1,
            "mysteries": [],
            "clues": [],
            "links": [],
        },
    }


def load_packet():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def fixture_digest():
    return hashlib.sha256(FIXTURE.read_bytes()).hexdigest()


def write_project(project_root, data):
    continuity = project_root / "continuity"
    continuity.mkdir(parents=True)
    for domain, relative_path in DATA_FILES.items():
        (project_root / relative_path).write_text(
            json.dumps(data[domain], ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )


def canonical_bytes(project_root):
    return {
        domain: (project_root / relative_path).read_bytes()
        for domain, relative_path in DATA_FILES.items()
    }


def continuity_entries(project_root):
    return sorted(path.name for path in (project_root / "continuity").iterdir())


class MergeStoryUpdatesTests(unittest.TestCase):
    def test_merge_script_parses_as_python_3_9(self):
        script = ROOT / "scripts" / "merge_story_updates.py"

        tree = ast.parse(
            script.read_text(encoding="utf-8"),
            filename=str(script),
            feature_version=(3, 9),
        )
        pep_604_unions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr)
        ]

        self.assertEqual(pep_604_unions, [])

    def test_upsert_replaces_in_place_and_appends_without_aliasing(self):
        existing = [{"id": "one", "value": "old"}, {"id": "two", "value": "keep"}]
        incoming = [{"id": "one", "value": "new"}, {"id": "three", "value": "add"}]

        result, added, updated = upsert_records(existing, incoming)

        self.assertEqual(
            result,
            [
                {"id": "one", "value": "new"},
                {"id": "two", "value": "keep"},
                {"id": "three", "value": "add"},
            ],
        )
        self.assertEqual((added, updated), (1, 1))
        result[0]["value"] = "mutated"
        self.assertEqual(existing[0]["value"], "old")
        self.assertEqual(incoming[0]["value"], "new")

    def test_merge_counts_and_content_for_all_six_collections(self):
        original_packet = load_packet()
        existing_packet = copy.deepcopy(original_packet)
        for key in (
            "timeline_events",
            "characters",
            "relationships",
            "mysteries",
            "clues",
            "clue_links",
        ):
            existing_packet[key][0]["source_refs"] = ["ch-000#old"]
        existing_packet["characters"][0]["notes"] = "outdated notes"
        data, _ = merge_update_packet(empty_data(), existing_packet)
        packet = copy.deepcopy(original_packet)
        additions = copy.deepcopy(original_packet)
        id_prefixes = {
            "timeline_events": "event-second",
            "characters": "char-second",
            "relationships": "rel-second-self",
            "mysteries": "mystery-second",
            "clues": "clue-second",
            "clue_links": "link-second",
        }
        for key, identifier in id_prefixes.items():
            additions[key][0]["id"] = identifier
            additions[key][0]["source_refs"] = ["ch-001#second"]
            packet[key].append(additions[key][0])
        additions["timeline_events"][0]["participants"] = ["char-second"]
        additions["relationships"][0]["source"] = "char-second"
        additions["relationships"][0]["target"] = "char-second"
        additions["clues"][0]["known_by"] = ["char-second"]
        additions["clue_links"][0]["source"] = "clue-second"
        additions["clue_links"][0]["target"] = "mystery-second"
        data_before = copy.deepcopy(data)
        packet_before = copy.deepcopy(packet)

        merged, summary = merge_update_packet(data, packet)

        self.assertEqual(data, data_before)
        self.assertEqual(packet, packet_before)
        for collection in ("events", "characters", "relationships", "mysteries", "clues", "links"):
            self.assertEqual(summary[collection + "_added"], 1)
            self.assertEqual(summary[collection + "_updated"], 1)
        merged_collections = {
            "timeline_events": merged["timeline"]["events"],
            "characters": merged["relationships"]["characters"],
            "relationships": merged["relationships"]["relationships"],
            "mysteries": merged["clues"]["mysteries"],
            "clues": merged["clues"]["clues"],
            "clue_links": merged["clues"]["links"],
        }
        for packet_key, records in merged_collections.items():
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]["source_refs"], original_packet[packet_key][0]["source_refs"])
            self.assertEqual(records[1]["id"], id_prefixes[packet_key])
        self.assertEqual(merged["relationships"]["characters"][0]["notes"], "Carries an unopened letter with her.")
        self.assertEqual(merged["clues"]["links"][1]["target"], "mystery-second")

    def test_invalid_merged_data_reports_every_validation_error(self):
        packet = load_packet()
        packet["timeline_events"][0]["participants"] = ["char-missing"]
        packet["clues"][0]["status"] = "impossible"

        with self.assertRaisesRegex(ValueError, r"^Invalid merged story data:\n") as caught:
            merge_update_packet(empty_data(), packet)

        message = str(caught.exception)
        self.assertIn("event-arrival.participants unknown character char-missing", message)
        self.assertIn("clue-brass-key.status has invalid value 'impossible'", message)

    def test_packet_can_repair_an_existing_record_before_validation(self):
        packet = load_packet()
        data, _ = merge_update_packet(empty_data(), packet)
        del data["relationships"]["characters"][0]["notes"]

        merged, summary = merge_update_packet(data, packet)

        self.assertEqual(summary["characters_updated"], 1)
        self.assertEqual(merged["relationships"]["characters"][0]["notes"], "Carries an unopened letter with her.")

    def test_packet_shape_errors_are_clear(self):
        cases = []
        missing = load_packet()
        del missing["clues"]
        cases.append((missing, "missing required key clues"))
        wrong_collection = load_packet()
        wrong_collection["characters"] = {}
        cases.append((wrong_collection, "characters must be a list"))
        missing_id = load_packet()
        del missing_id["mysteries"][0]["id"]
        cases.append((missing_id, "mysteries[0] must contain a string id"))
        bad_chapter = load_packet()
        bad_chapter["chapter"] = "chapter one"
        cases.append((bad_chapter, "chapter must be a valid chapter id"))

        for packet, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaises(ValueError) as caught:
                    merge_update_packet(empty_data(), packet)
                self.assertIn(expected, str(caught.exception))

    def test_dry_run_prints_json_summary_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            write_project(project_root, empty_data())
            before = canonical_bytes(project_root)

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/merge_story_updates.py",
                    str(project_root),
                    str(FIXTURE),
                    "--expected-sha256",
                    fixture_digest(),
                    "--dry-run",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            after = canonical_bytes(project_root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, after)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["events_added"], 1)
        self.assertEqual(summary["characters_added"], 1)
        self.assertEqual(summary["links_updated"], 0)

    def test_legacy_cli_without_digest_still_merges(self):
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            write_project(project_root, empty_data())

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/merge_story_updates.py",
                    str(project_root),
                    str(FIXTURE),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            merged = json.loads(
                (project_root / DATA_FILES["timeline"]).read_text(encoding="utf-8")
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(merged["events"][0]["id"], "event-arrival")

    def test_legacy_cli_without_digest_still_dry_runs_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            write_project(project_root, empty_data())
            before = canonical_bytes(project_root)

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/merge_story_updates.py",
                    str(project_root),
                    str(FIXTURE),
                    "--dry-run",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            after = canonical_bytes(project_root)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, after)
        self.assertEqual(json.loads(result.stdout)["events_added"], 1)

    def test_cli_digest_mismatch_is_clear_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            write_project(project_root, empty_data())
            before = canonical_bytes(project_root)

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/merge_story_updates.py",
                    str(project_root),
                    str(FIXTURE),
                    "--expected-sha256",
                    "0" * 64,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            after = canonical_bytes(project_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERROR: update packet SHA-256 mismatch", result.stderr)
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        self.assertEqual(before, after)

    def test_cli_matching_digest_merges_the_verified_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            write_project(project_root, empty_data())

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/merge_story_updates.py",
                    str(project_root),
                    str(FIXTURE),
                    "--expected-sha256",
                    fixture_digest(),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            merged = json.loads(
                (project_root / DATA_FILES["timeline"]).read_text(encoding="utf-8")
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(merged["events"][0]["id"], "event-arrival")

    def test_digest_confirmed_merge_rejects_continuity_symlink_without_external_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_root = root / "project"
            external_project = root / "external"
            project_root.mkdir()
            write_project(external_project, empty_data())
            (project_root / "continuity").symlink_to(
                external_project / "continuity",
                target_is_directory=True,
            )
            before = canonical_bytes(external_project)

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/merge_story_updates.py",
                    str(project_root),
                    str(FIXTURE),
                    "--expected-sha256",
                    fixture_digest(),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            after = canonical_bytes(external_project)
            external_entries = continuity_entries(external_project)
            project_entries = sorted(path.name for path in project_root.iterdir())

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERROR:", result.stderr)
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        self.assertEqual(before, after)
        self.assertEqual(
            external_entries,
            ["clues.json", "relationships.json", "timeline.json"],
        )
        self.assertEqual(project_entries, ["continuity"])

    def test_digest_confirmed_merge_rejects_each_canonical_leaf_symlink(self):
        for domain, relative_path in DATA_FILES.items():
            with self.subTest(domain=domain), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                project_root = root / "project"
                external_project = root / "external"
                write_project(project_root, empty_data())
                write_project(external_project, empty_data())
                target = project_root / relative_path
                target.unlink()
                target.symlink_to(external_project / relative_path)
                before = canonical_bytes(external_project)

                result = subprocess.run(
                    [
                        sys.executable,
                        "scripts/merge_story_updates.py",
                        str(project_root),
                        str(FIXTURE),
                        "--expected-sha256",
                        fixture_digest(),
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )

                after = canonical_bytes(external_project)
                external_entries = continuity_entries(external_project)
                project_entries = continuity_entries(project_root)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ERROR:", result.stderr)
            self.assertNotIn("Traceback", result.stdout + result.stderr)
            self.assertEqual(before, after)
            self.assertEqual(
                external_entries,
                ["clues.json", "relationships.json", "timeline.json"],
            )
            self.assertEqual(
                project_entries,
                ["clues.json", "relationships.json", "timeline.json"],
            )

    def test_verified_packet_is_read_once_and_parsed_from_those_bytes(self):
        packet_bytes = FIXTURE.read_bytes()
        update_path = mock.Mock()
        update_path.read_bytes.return_value = packet_bytes

        packet = read_verified_packet(
            update_path,
            hashlib.sha256(packet_bytes).hexdigest(),
        )

        update_path.read_bytes.assert_called_once_with()
        self.assertEqual(packet, json.loads(packet_bytes))

    def test_cli_packet_error_has_no_traceback(self):
        invalid_packet = load_packet()
        del invalid_packet["characters"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_root = root / "project"
            update_path = root / "update.json"
            write_project(project_root, empty_data())
            update_path.write_text(json.dumps(invalid_packet), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/merge_story_updates.py",
                    str(project_root),
                    str(update_path),
                    "--expected-sha256",
                    hashlib.sha256(update_path.read_bytes()).hexdigest(),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERROR: update packet missing required key characters", result.stderr)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_second_replace_failure_restores_all_original_bytes_and_cleans_artifacts(self):
        packet = load_packet()
        merged, _ = merge_update_packet(empty_data(), packet)
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            write_project(project_root, empty_data())
            before = canonical_bytes(project_root)
            continuity = project_root / "continuity"
            original_replace = os.replace
            failed = False

            def fail_second_canonical(source, destination, *arguments, **keywords):
                nonlocal failed
                if Path(destination).name == "relationships.json" and not failed:
                    failed = True
                    raise OSError("simulated second replace failure")
                return original_replace(
                    source,
                    destination,
                    *arguments,
                    **keywords,
                )

            with mock.patch("scripts.story_data.os.replace", side_effect=fail_second_canonical):
                with self.assertRaisesRegex(OSError, "simulated second replace failure"):
                    write_story_data_atomic(project_root, merged)

            after = canonical_bytes(project_root)
            remaining = sorted(path.name for path in continuity.iterdir())

        self.assertEqual(before, after)
        self.assertEqual(remaining, ["clues.json", "relationships.json", "timeline.json"])

    def test_directory_swap_before_publish_is_rejected_without_external_writes(self):
        packet = load_packet()
        merged, _ = merge_update_packet(empty_data(), packet)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_root = root / "project"
            external_project = root / "external"
            write_project(project_root, empty_data())
            write_project(external_project, empty_data())
            before = canonical_bytes(external_project)
            continuity = project_root / "continuity"
            moved = root / "continuity-original"
            original_replace = os.replace
            swapped = False

            def swap_before_first_publish(source, destination, *arguments, **keywords):
                nonlocal swapped
                source_name = Path(source).name
                destination_name = Path(destination).name
                if (
                    not swapped
                    and source_name.endswith(".tmp")
                    and destination_name in {
                        "timeline.json",
                        "relationships.json",
                        "clues.json",
                    }
                ):
                    continuity.rename(moved)
                    continuity.symlink_to(
                        external_project / "continuity",
                        target_is_directory=True,
                    )
                    for artifact in moved.iterdir():
                        if artifact.name.startswith("."):
                            shutil.copyfile(
                                artifact,
                                external_project / "continuity" / artifact.name,
                            )
                    swapped = True
                return original_replace(
                    source,
                    destination,
                    *arguments,
                    **keywords,
                )

            with mock.patch(
                "scripts.story_data.os.replace",
                side_effect=swap_before_first_publish,
            ):
                with self.assertRaisesRegex(OSError, "directory changed"):
                    write_story_data_atomic(project_root, merged)

            after = canonical_bytes(external_project)
            original_entries = sorted(path.name for path in moved.iterdir())

        self.assertTrue(swapped)
        self.assertEqual(before, after)
        self.assertEqual(
            original_entries,
            ["clues.json", "relationships.json", "timeline.json"],
        )

    def test_restore_failure_preserves_original_backup_and_reports_exact_path(self):
        packet = load_packet()
        merged, _ = merge_update_packet(empty_data(), packet)
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            write_project(project_root, empty_data())
            before = canonical_bytes(project_root)
            continuity = project_root / "continuity"
            original_replace = os.replace
            publish_failed = False
            failed_backup_path = None

            def fail_publish_and_timeline_restore(
                source,
                destination,
                *arguments,
                **keywords,
            ):
                nonlocal publish_failed, failed_backup_path
                source_path = Path(source)
                destination_path = Path(destination)
                if (
                    source_path.suffix == ".tmp"
                    and destination_path.name == "relationships.json"
                    and not publish_failed
                ):
                    publish_failed = True
                    raise OSError("simulated publish failure")
                if source_path.suffix == ".bak" and destination_path.name == "timeline.json":
                    failed_backup_path = continuity / source_path
                    raise OSError("simulated timeline restore failure")
                return original_replace(
                    source,
                    destination,
                    *arguments,
                    **keywords,
                )

            with mock.patch(
                "scripts.story_data.os.replace",
                side_effect=fail_publish_and_timeline_restore,
            ):
                with self.assertRaises(RuntimeError) as caught:
                    write_story_data_atomic(project_root, merged)

            self.assertIsNotNone(failed_backup_path)
            self.assertTrue(failed_backup_path.exists())
            self.assertEqual(failed_backup_path.read_bytes(), before["timeline"])
            self.assertIn("simulated timeline restore failure", str(caught.exception))
            self.assertIn(str(failed_backup_path), str(caught.exception))
            self.assertIsInstance(caught.exception.__cause__, OSError)
            self.assertIn("simulated publish failure", str(caught.exception.__cause__))
            self.assertEqual(canonical_bytes(project_root)["relationships"], before["relationships"])
            self.assertEqual(canonical_bytes(project_root)["clues"], before["clues"])
            artifacts = [
                path for path in continuity.iterdir()
                if path.name not in {"timeline.json", "relationships.json", "clues.json"}
            ]

        self.assertEqual(artifacts, [failed_backup_path])

    def test_keyboard_interrupt_rolls_back_all_files_and_is_reraised(self):
        packet = load_packet()
        merged, _ = merge_update_packet(empty_data(), packet)
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            write_project(project_root, empty_data())
            before = canonical_bytes(project_root)
            continuity = project_root / "continuity"
            original_replace = os.replace
            interrupted = False

            def interrupt_second_publish(source, destination, *arguments, **keywords):
                nonlocal interrupted
                if (
                    Path(source).suffix == ".tmp"
                    and Path(destination).name == "relationships.json"
                    and not interrupted
                ):
                    interrupted = True
                    raise KeyboardInterrupt("simulated publish interrupt")
                return original_replace(
                    source,
                    destination,
                    *arguments,
                    **keywords,
                )

            with mock.patch(
                "scripts.story_data.os.replace",
                side_effect=interrupt_second_publish,
            ):
                with self.assertRaises(KeyboardInterrupt) as caught:
                    write_story_data_atomic(project_root, merged)

            after = canonical_bytes(project_root)
            remaining = sorted(path.name for path in continuity.iterdir())

        self.assertEqual(str(caught.exception), "simulated publish interrupt")
        self.assertEqual(before, after)
        self.assertEqual(remaining, ["clues.json", "relationships.json", "timeline.json"])

    def test_atomic_write_rejects_invalid_data_before_touching_files(self):
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            write_project(project_root, empty_data())
            before = canonical_bytes(project_root)
            invalid = empty_data()
            invalid["timeline"]["schema_version"] = 99

            with self.assertRaisesRegex(ValueError, r"^Invalid story data:\n"):
                write_story_data_atomic(project_root, invalid)

            self.assertEqual(before, canonical_bytes(project_root))


if __name__ == "__main__":
    unittest.main()
