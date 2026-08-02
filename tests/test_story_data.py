import tempfile
import unittest
from pathlib import Path
import subprocess
import sys
import json

from scripts.init_project import initialize_project
from scripts.render_dashboard import render_dashboard
from scripts.story_data import atomic_write_json, filter_visibility, validate_story_data


def empty_data():
    return {
        "timeline": {"schema_version": 1, "events": []},
        "relationships": {
            "schema_version": 1,
            "characters": [],
            "relationships": [],
        },
        "clues": {"schema_version": 1, "mysteries": [], "clues": [], "links": []},
    }


def character(character_id="char-lin"):
    return {
        "id": character_id,
        "name": "Lin",
        "aliases": [],
        "role": "protagonist",
        "faction": "archive",
        "status": "active",
        "first_chapter": "ch-01",
        "notes": "",
        "visibility": "author",
        "source_refs": ["ch-01"],
    }


def event():
    return {
        "id": "event-return",
        "title": "Return",
        "story_time": "2030-01-01",
        "sequence": 1,
        "chapter": "ch-01",
        "location": "Harbor",
        "participants": ["char-missing"],
        "summary": "A return.",
        "causes": [],
        "effects": [],
        "kind": "present",
        "certainty": "confirmed",
        "visibility": "author",
        "source_refs": ["ch-01#return"],
    }


def fixture_data():
    fixture = Path(__file__).resolve().parent / "fixtures" / "chapter-001-update.json"
    packet = json.loads(fixture.read_text(encoding="utf-8"))
    return {
        "timeline": {"schema_version": 1, "events": packet["timeline_events"]},
        "relationships": {
            "schema_version": 1,
            "characters": packet["characters"],
            "relationships": packet["relationships"],
        },
        "clues": {
            "schema_version": 1,
            "mysteries": packet["mysteries"],
            "clues": packet["clues"],
            "links": packet["clue_links"],
        },
    }


class StoryDataTests(unittest.TestCase):
    def test_valid_empty_data(self):
        self.assertEqual(validate_story_data(empty_data()), [])

    def test_duplicate_character_id_is_reported(self):
        data = empty_data()
        data["relationships"]["characters"] = [character(), character()]
        self.assertIn("duplicate id char-lin", validate_story_data(data))

    def test_unknown_timeline_participant_is_reported(self):
        data = empty_data()
        data["timeline"]["events"] = [event()]
        errors = validate_story_data(data)
        self.assertTrue(any("event-return" in error and "unknown character char-missing" in error for error in errors))

    def test_timeline_event_references_require_existing_non_empty_canonical_ids(self):
        cases = (
            ("causes", "event-missing", "event-arrival.causes unknown canonical record event-missing"),
            ("effects", "event-missing", "event-arrival.effects unknown canonical record event-missing"),
            ("causes", "", "event-arrival.causes must contain non-empty canonical record ids"),
            ("effects", "", "event-arrival.effects must contain non-empty canonical record ids"),
        )

        for field, value, expected in cases:
            with self.subTest(field=field, value=value):
                data = fixture_data()
                data["timeline"]["events"][0][field] = [value]

                self.assertIn(expected, validate_story_data(data))

    def test_timeline_event_references_allow_existing_cross_domain_records(self):
        data = fixture_data()
        event_record = data["timeline"]["events"][0]
        self.assertEqual(event_record["effects"], ["clue-brass-key"])
        event_record["causes"] = ["char-lin"]

        self.assertEqual(validate_story_data(data), [])

    def test_timeline_event_reference_errors_accumulate_with_malformed_values(self):
        data = fixture_data()
        event_record = data["timeline"]["events"][0]
        event_record["causes"] = ["event-missing", {}]
        event_record["effects"] = {}

        errors = validate_story_data(data)

        self.assertIn("event-arrival.causes must be a list of strings", errors)
        self.assertIn("event-arrival.causes unknown canonical record event-missing", errors)
        self.assertIn("event-arrival.effects must be a list of strings", errors)

    def test_illegal_clue_status_is_reported(self):
        data = empty_data()
        data["clues"]["clues"] = [{
            "id": "clue-key",
            "title": "Key",
            "description": "A key.",
            "status": "invalid",
            "introduced_chapter": "ch-01",
            "known_by": [],
            "planned_payoff": "ch-02",
            "actual_payoff": "",
            "certainty": "author-planned",
            "visibility": "author",
            "source_refs": ["ch-01#key"],
        }]
        errors = validate_story_data(data)
        self.assertTrue(any("clue-key" in error and "status" in error for error in errors))

    def test_missing_relationship_endpoint_is_reported(self):
        data = empty_data()
        data["relationships"]["relationships"] = [{
            "id": "rel-lin-mentor",
            "source": "char-lin",
            "target": "char-mentor",
            "type": "mentor",
            "direction": "directed",
            "status": "active",
            "start_chapter": "ch-01",
            "end_chapter": "",
            "description": "Mentors Lin.",
            "certainty": "confirmed",
            "visibility": "author",
            "source_refs": ["ch-01"],
        }]
        errors = validate_story_data(data)
        self.assertTrue(any("rel-lin-mentor" in error and "char-lin" in error for error in errors))
        self.assertTrue(any("rel-lin-mentor" in error and "char-mentor" in error for error in errors))

    def test_missing_clue_link_endpoint_is_reported(self):
        data = empty_data()
        data["clues"]["links"] = [{
            "id": "link-mystery-key",
            "source": "mystery-missing",
            "target": "clue-key",
            "type": "supports",
            "certainty": "inferred",
            "visibility": "author",
            "source_refs": ["ch-01"],
        }]
        errors = validate_story_data(data)
        self.assertTrue(any("link-mystery-key" in error and "mystery-missing" in error for error in errors))
        self.assertTrue(any("link-mystery-key" in error and "clue-key" in error for error in errors))

    def test_clue_link_cannot_reference_another_clue_link(self):
        data = empty_data()
        data["clues"]["links"] = [{
            "id": "link-first",
            "source": "link-second",
            "target": "link-second",
            "type": "supports",
            "certainty": "inferred",
            "visibility": "author",
            "source_refs": ["ch-01"],
        }, {
            "id": "link-second",
            "source": "link-first",
            "target": "link-first",
            "type": "supports",
            "certainty": "inferred",
            "visibility": "author",
            "source_refs": ["ch-01"],
        }]
        errors = validate_story_data(data)
        self.assertTrue(any("link-first" in error and "link-second" in error for error in errors))

    def test_illegal_schema_version_is_reported(self):
        data = empty_data()
        data["timeline"]["schema_version"] = 2
        self.assertIn("timeline.schema_version must be 1", validate_story_data(data))

    def test_atomic_write_json_uses_readable_utf8_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "story.json"
            atomic_write_json(path, {"title": "春天"})
            self.assertEqual(path.read_text(encoding="utf-8"), '{\n  "title": "春天"\n}\n')

    def test_cli_invalid_utf8_is_a_clear_error_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            continuity = root / "continuity"
            continuity.mkdir()
            (continuity / "timeline.json").write_bytes(b"\xff")
            result = subprocess.run(
                [sys.executable, "scripts/validate_story_data.py", str(root)],
                cwd=Path(__file__).resolve().parent.parent,
                capture_output=True,
                text=True,
            )
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERROR:", output)
        self.assertNotIn("Traceback", output)

    def test_unhashable_enum_and_reference_values_return_errors(self):
        data = empty_data()
        malformed_event = event()
        malformed_event["kind"] = []
        malformed_event["participants"] = [{}]
        data["timeline"]["events"] = [malformed_event]
        data["relationships"]["relationships"] = [{
            "id": "rel-broken",
            "source": [],
            "target": {},
            "type": "unknown",
            "direction": "directed",
            "status": "active",
            "start_chapter": "ch-01",
            "end_chapter": "",
            "description": "Broken endpoints.",
            "certainty": "confirmed",
            "visibility": "author",
            "source_refs": ["ch-01"],
        }]
        data["clues"]["clues"] = [{
            "id": "clue-broken",
            "title": "Broken clue",
            "description": "Contains invalid values.",
            "status": {},
            "introduced_chapter": "ch-01",
            "known_by": [[]],
            "planned_payoff": "",
            "actual_payoff": "",
            "certainty": "confirmed",
            "visibility": "author",
            "source_refs": ["ch-01"],
        }]
        data["clues"]["links"] = [{
            "id": "link-broken",
            "source": [],
            "target": {},
            "type": "supports",
            "certainty": "confirmed",
            "visibility": "author",
            "source_refs": ["ch-01"],
        }]
        errors = validate_story_data(data)
        self.assertTrue(any("event-return.kind" in error for error in errors))
        self.assertTrue(any("event-return.participants" in error for error in errors))
        self.assertTrue(any("rel-broken.source" in error for error in errors))
        self.assertTrue(any("rel-broken.target" in error for error in errors))
        self.assertTrue(any("clue-broken.status" in error for error in errors))
        self.assertTrue(any("clue-broken.known_by" in error for error in errors))
        self.assertTrue(any("link-broken.source" in error for error in errors))
        self.assertTrue(any("link-broken.target" in error for error in errors))

    def test_reviewer_character_type_counterexamples_are_all_reported(self):
        data = empty_data()
        malformed = character()
        malformed["name"] = []
        malformed["aliases"] = {}
        malformed["role"] = 17
        malformed["first_chapter"] = {"bad": 1}
        data["relationships"]["characters"] = [malformed]

        errors = validate_story_data(data)

        self.assertTrue(errors)
        self.assertTrue(any("char-lin.name must be a string" in error for error in errors))
        self.assertTrue(any("char-lin.aliases must be a list of strings" in error for error in errors))
        self.assertTrue(any("char-lin.role must be a string" in error for error in errors))
        self.assertTrue(any("char-lin.first_chapter must be a string" in error for error in errors))

    def test_all_six_record_types_reject_malformed_json_values(self):
        mutations = (
            ("event sequence bool", lambda data: data["timeline"]["events"][0].__setitem__("sequence", True)),
            ("event causes object", lambda data: data["timeline"]["events"][0].__setitem__("causes", {})),
            ("character aliases object", lambda data: data["relationships"]["characters"][0].__setitem__("aliases", {})),
            ("relationship description array", lambda data: data["relationships"]["relationships"][0].__setitem__("description", [])),
            ("mystery resolved chapter object", lambda data: data["clues"]["mysteries"][0].__setitem__("resolved_chapter", {})),
            ("clue known by object", lambda data: data["clues"]["clues"][0].__setitem__("known_by", {})),
            ("link source array", lambda data: data["clues"]["links"][0].__setitem__("source", [])),
            ("schema bool", lambda data: data["timeline"].__setitem__("schema_version", True)),
        )

        for label, mutate in mutations:
            with self.subTest(label=label):
                data = fixture_data()
                mutate(data)
                self.assertTrue(validate_story_data(data))
                for mode in ("author", "reader"):
                    with self.subTest(mode=mode):
                        with self.assertRaises(ValueError):
                            filter_visibility(data, mode)

    def test_author_and_reader_render_fail_at_validation_for_malformed_json_values(self):
        mutations = (
            lambda data: data["timeline"]["events"][0].__setitem__("participants", {}),
            lambda data: data["relationships"]["characters"][0].__setitem__("name", []),
            lambda data: data["relationships"]["relationships"][0].__setitem__("type", 17),
            lambda data: data["clues"]["mysteries"][0].__setitem__("question", None),
            lambda data: data["clues"]["clues"][0].__setitem__("actual_payoff", []),
            lambda data: data["clues"]["links"][0].__setitem__("source_refs", {}),
        )
        with tempfile.TemporaryDirectory() as directory:
            project = initialize_project(Path(directory) / "project", "Malformed")
            for index, mutate in enumerate(mutations):
                with self.subTest(index=index):
                    data = fixture_data()
                    mutate(data)
                    for domain in ("timeline", "relationships", "clues"):
                        (project / "continuity" / (domain + ".json")).write_text(
                            json.dumps(data[domain], ensure_ascii=False),
                            encoding="utf-8",
                        )
                    for mode in ("author", "reader"):
                        output = project / "visualizations" / (mode + ".html")
                        with self.subTest(mode=mode):
                            with self.assertRaisesRegex(ValueError, "Invalid story data"):
                                render_dashboard(project, output, mode=mode)

    def test_character_and_mystery_reject_presentation_certainty_fields(self):
        data = fixture_data()
        data["relationships"]["characters"][0]["candidate_certainty"] = "confirmed"
        data["clues"]["mysteries"][0]["certainty"] = "inferred"

        errors = validate_story_data(data)

        self.assertTrue(any("candidate_certainty is not a canonical field" in error for error in errors))
        self.assertTrue(any("certainty is not a canonical field" in error for error in errors))

    def test_cli_malformed_semantic_json_is_a_clear_error_without_traceback(self):
        data = empty_data()
        malformed_event = event()
        malformed_event["kind"] = []
        data["timeline"]["events"] = [malformed_event]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            continuity = root / "continuity"
            continuity.mkdir()
            for filename, value in (
                ("timeline.json", data["timeline"]),
                ("relationships.json", data["relationships"]),
                ("clues.json", data["clues"]),
            ):
                (continuity / filename).write_text(json.dumps(value), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "scripts/validate_story_data.py", str(root)],
                cwd=Path(__file__).resolve().parent.parent,
                capture_output=True,
                text=True,
            )
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERROR: event-return.kind", output)
        self.assertNotIn("Traceback", output)
