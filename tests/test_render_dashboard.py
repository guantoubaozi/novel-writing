import ast
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import shutil

from scripts.init_project import initialize_project
from scripts.render_dashboard import (
    _select_story_views,
    json_for_html,
    render_dashboard,
)
from scripts.story_data import filter_visibility


SKILL_ROOT = Path(__file__).resolve().parent.parent


def write_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def dashboard_payload(html):
    marker = "const storyData = "
    start = html.index(marker) + len(marker)
    payload, _end = json.JSONDecoder().raw_decode(html[start:])
    return payload


def story_record_ids(story):
    return {
        record["id"]
        for domain, collection in (
            ("timeline", "events"),
            ("relationships", "characters"),
            ("relationships", "relationships"),
            ("clues", "mysteries"),
            ("clues", "clues"),
            ("clues", "links"),
        )
        for record in story[domain][collection]
    }


def story_dependency_ids(story):
    dependencies = set()
    for event_record in story["timeline"]["events"]:
        for field in ("participants", "causes", "effects"):
            dependencies.update(event_record[field])
    for relationship_record in story["relationships"]["relationships"]:
        dependencies.update(
            (relationship_record["source"], relationship_record["target"])
        )
    for clue_record in story["clues"]["clues"]:
        dependencies.update(clue_record["known_by"])
    for link_record in story["clues"]["links"]:
        dependencies.update((link_record["source"], link_record["target"]))
    dependencies.discard("")
    return dependencies


def populated_data():
    return {
        "timeline": {
            "schema_version": 1,
            "events": [
                {
                    "id": "event-arrival",
                    "title": "抵达",
                    "story_time": "2032-03-04",
                    "sequence": 1,
                    "chapter": "ch-01",
                    "location": "旧港",
                    "participants": ["char-lan", "char-secret"],
                    "summary": "林岚看见 </script><script>alert('x')</script>",
                    "causes": ["event-secret"],
                    "effects": ["event-secret"],
                    "kind": "present",
                    "certainty": "confirmed",
                    "visibility": "spoiler-safe",
                    "source_refs": ["ch-01#arrival"],
                },
                {
                    "id": "event-secret",
                    "title": "幕后真相",
                    "story_time": "2032-03-03",
                    "sequence": 0,
                    "chapter": "ch-01",
                    "location": "档案室",
                    "participants": ["char-secret"],
                    "summary": "只供作者查看",
                    "causes": [],
                    "effects": ["event-arrival"],
                    "kind": "flashback",
                    "certainty": "author-planned",
                    "visibility": "author",
                    "source_refs": ["ch-01#secret"],
                },
                {
                    "id": "event-mislabelled-plan",
                    "title": "误标计划",
                    "story_time": "",
                    "sequence": 2,
                    "chapter": "ch-02",
                    "location": "",
                    "participants": ["char-lan"],
                    "summary": "即使误标也不能泄露",
                    "causes": [],
                    "effects": [],
                    "kind": "flashforward",
                    "certainty": "author-planned",
                    "visibility": "spoiler-safe",
                    "source_refs": ["ch-02"],
                },
            ],
        },
        "relationships": {
            "schema_version": 1,
            "characters": [
                {
                    "id": "char-lan",
                    "name": "林岚",
                    "aliases": ["SECRET_ALIAS"],
                    "role": "SECRET_ROLE",
                    "faction": "SECRET_FACTION",
                    "status": "active",
                    "first_chapter": "ch-99",
                    "notes": "SECRET_NOTES",
                    "visibility": "spoiler-safe",
                    "source_refs": ["ch-99#ending"],
                },
                {
                    "id": "char-wu",
                    "name": "吴砚",
                    "aliases": [],
                    "role": "同伴",
                    "faction": "调查组",
                    "status": "active",
                    "first_chapter": "ch-01",
                    "notes": "",
                    "visibility": "spoiler-safe",
                    "source_refs": ["ch-01"],
                },
                {
                    "id": "char-secret",
                    "name": "幕后人",
                    "aliases": [],
                    "role": "反派",
                    "faction": "未知",
                    "status": "unknown",
                    "first_chapter": "ch-01",
                    "notes": "隐藏身份",
                    "visibility": "author",
                    "source_refs": ["ch-01#secret"],
                },
            ],
            "relationships": [
                {
                    "id": "rel-lan-wu",
                    "source": "char-lan",
                    "target": "char-wu",
                    "type": "同伴",
                    "direction": "mutual",
                    "status": "active",
                    "start_chapter": "ch-01",
                    "end_chapter": "ch-99",
                    "description": "共同调查",
                    "certainty": "confirmed",
                    "visibility": "spoiler-safe",
                    "source_refs": ["ch-99#ending"],
                },
                {
                    "id": "rel-lan-secret",
                    "source": "char-lan",
                    "target": "char-secret",
                    "type": "对手",
                    "direction": "directed",
                    "status": "hidden",
                    "start_chapter": "ch-01",
                    "end_chapter": "",
                    "description": "尚未公开",
                    "certainty": "confirmed",
                    "visibility": "spoiler-safe",
                    "source_refs": ["ch-01"],
                }
            ],
        },
        "clues": {
            "schema_version": 1,
            "mysteries": [
                {
                    "id": "mystery-clock",
                    "title": "停摆的钟",
                    "question": "为何停在三点？",
                    "status": "open",
                    "introduced_chapter": "ch-01",
                    "resolved_chapter": "",
                    "visibility": "spoiler-safe",
                    "source_refs": ["ch-01"],
                },
                {
                    "id": "mystery-door",
                    "title": "锁住的门",
                    "question": "谁锁了门？",
                    "status": "open",
                    "introduced_chapter": "ch-02",
                    "resolved_chapter": "",
                    "visibility": "spoiler-safe",
                    "source_refs": ["ch-02"],
                }
            ],
            "clues": [
                {
                    "id": "clue-dust",
                    "title": "灰尘",
                    "description": "表盘没有灰尘",
                    "status": "noticed",
                    "introduced_chapter": "ch-01",
                    "known_by": ["char-lan", "char-secret"],
                    "planned_payoff": "SECRET_PLANNED_PAYOFF",
                    "actual_payoff": "SECRET_UNRESOLVED_ACTUAL",
                    "certainty": "confirmed",
                    "visibility": "spoiler-safe",
                    "source_refs": ["ch-99#ending"],
                },
                {
                    "id": "clue-fiber",
                    "title": "门锁纤维",
                    "description": "锁孔里有纤维",
                    "status": "seeded",
                    "introduced_chapter": "ch-02",
                    "known_by": ["char-wu"],
                    "planned_payoff": "SECRET_SECOND_PAYOFF",
                    "actual_payoff": "",
                    "certainty": "confirmed",
                    "visibility": "spoiler-safe",
                    "source_refs": ["ch-02#door"],
                }
            ],
            "links": [
                {
                    "id": "link-clock-dust",
                    "source": "mystery-clock",
                    "target": "clue-dust",
                    "type": "supports",
                    "certainty": "confirmed",
                    "visibility": "spoiler-safe",
                    "source_refs": ["ch-01#clock"],
                },
                {
                    "id": "link-dust-secret",
                    "source": "clue-dust",
                    "target": "char-secret",
                    "type": "possessed-by",
                    "certainty": "confirmed",
                    "visibility": "spoiler-safe",
                    "source_refs": ["ch-01#secret"],
                },
                {
                    "id": "link-mystery-rel",
                    "source": "mystery-clock",
                    "target": "rel-lan-secret",
                    "type": "points-to",
                    "certainty": "confirmed",
                    "visibility": "spoiler-safe",
                    "source_refs": ["ch-01#secret"],
                },
                {
                    "id": "link-door-fiber",
                    "source": "mystery-door",
                    "target": "clue-fiber",
                    "type": "supports",
                    "certainty": "confirmed",
                    "visibility": "spoiler-safe",
                    "source_refs": ["ch-02#door"],
                },
            ],
        },
    }


def event_link_dependency_data():
    data = populated_data()
    event = data["timeline"]["events"][0]
    event["causes"] = ["link-clock-dust"]
    event["effects"] = ["link-door-fiber"]
    return data


class DashboardTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.project = initialize_project(
            Path(self.temporary_directory.name) / "project",
            '<雾城 & "梦">',
        )
        self.data = populated_data()
        for name in ("timeline", "relationships", "clues"):
            write_json(
                self.project / "continuity" / (name + ".json"),
                self.data[name],
            )


class VisibilityTests(unittest.TestCase):
    def test_author_mode_returns_equal_deep_copy_without_mutating_input(self):
        data = populated_data()
        original = copy.deepcopy(data)

        filtered = filter_visibility(data, "author")
        filtered["timeline"]["events"][0]["title"] = "changed"

        self.assertEqual(data, original)
        self.assertNotEqual(filtered, data)

    def test_reader_mode_removes_hidden_records_and_dangling_references(self):
        filtered = filter_visibility(populated_data(), "reader")

        self.assertEqual(
            [event["id"] for event in filtered["timeline"]["events"]],
            ["event-reader-001"],
        )
        event = filtered["timeline"]["events"][0]
        self.assertEqual(len(event["participants"]), 1)
        self.assertNotEqual(event["participants"], ["char-lan"])
        self.assertEqual(event["causes"], [])
        self.assertEqual(event["effects"], [])
        character_ids = [
            item["id"] for item in filtered["relationships"]["characters"]
        ]
        self.assertEqual(len(character_ids), 2)
        self.assertTrue(all(identifier.startswith("char-reader-") for identifier in character_ids))
        relationship = filtered["relationships"]["relationships"][0]
        self.assertIn(relationship["source"], character_ids)
        self.assertIn(relationship["target"], character_ids)
        self.assertNotEqual(relationship["source"], relationship["target"])
        self.assertEqual(
            filtered["clues"]["clues"][0]["known_by"],
            [event["participants"][0]],
        )
        link_ids = [item["id"] for item in filtered["clues"]["links"]]
        self.assertEqual(len(link_ids), 2)
        self.assertTrue(all(identifier.startswith("link-reader-") for identifier in link_ids))
        self.assertEqual(filtered["timeline"]["schema_version"], 1)

    def test_author_and_reader_keep_event_dependencies_on_visible_clue_links(self):
        data = event_link_dependency_data()

        author = filter_visibility(data, "author")
        author_event = author["timeline"]["events"][0]
        self.assertEqual(author_event["causes"], ["link-clock-dust"])
        self.assertEqual(author_event["effects"], ["link-door-fiber"])

        reader = filter_visibility(data, "reader")
        reader_event = reader["timeline"]["events"][0]
        reader_link_ids = {
            record["id"] for record in reader["clues"]["links"]
        }
        self.assertEqual(len(reader_event["causes"]), 1)
        self.assertEqual(len(reader_event["effects"]), 1)
        self.assertTrue(reader_event["causes"][0].startswith("link-reader-"))
        self.assertTrue(reader_event["effects"][0].startswith("link-reader-"))
        self.assertLessEqual(
            set(reader_event["causes"] + reader_event["effects"]),
            reader_link_ids,
        )
        self.assertLessEqual(story_dependency_ids(reader), story_record_ids(reader))

    def test_reader_drops_event_to_link_dependency_when_endpoint_is_hidden(self):
        data = event_link_dependency_data()
        data["clues"]["clues"][0]["visibility"] = "author"

        reader = filter_visibility(data, "reader")
        reader_event = reader["timeline"]["events"][0]

        self.assertEqual(reader_event["causes"], [])
        self.assertEqual(len(reader_event["effects"]), 1)
        self.assertLessEqual(story_dependency_ids(reader), story_record_ids(reader))

    def test_reader_mode_redacts_author_fields_and_semantic_identifiers(self):
        filtered = filter_visibility(populated_data(), "reader")
        serialized = json.dumps(filtered, ensure_ascii=False)

        for secret in (
            "SECRET_ALIAS",
            "SECRET_ROLE",
            "SECRET_FACTION",
            "SECRET_NOTES",
            "SECRET_PLANNED_PAYOFF",
            "SECRET_UNRESOLVED_ACTUAL",
            "SECRET_SECOND_PAYOFF",
            "ch-99",
            "ending",
            "char-lan",
            "char-wu",
            "rel-lan-wu",
            "mystery-clock",
            "clue-dust",
            "link-clock-dust",
        ):
            self.assertNotIn(secret, serialized)
        character = filtered["relationships"]["characters"][0]
        self.assertEqual(character["aliases"], [])
        self.assertEqual(character["role"], "")
        self.assertEqual(character["faction"], "")
        self.assertEqual(character["notes"], "")
        self.assertEqual(character["source_refs"], [])
        clue = filtered["clues"]["clues"][0]
        self.assertEqual(clue["planned_payoff"], "")
        self.assertEqual(clue["actual_payoff"], "")
        self.assertEqual(clue["source_refs"], [])

    def test_reader_keeps_actual_payoff_only_for_resolved_clue(self):
        data = populated_data()
        data["clues"]["clues"][0]["status"] = "resolved"
        data["clues"]["clues"][0]["actual_payoff"] = "公开答案"

        filtered = filter_visibility(data, "reader")

        self.assertEqual(filtered["clues"]["clues"][0]["actual_payoff"], "公开答案")

    def test_unknown_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "mode"):
            filter_visibility(populated_data(), "preview")


class JsonEmbeddingTests(unittest.TestCase):
    def test_json_for_html_escapes_script_breakout_and_unicode_separators(self):
        encoded = json_for_html({"value": "</script>&>\u2028\u2029"})

        self.assertNotIn("<", encoded)
        self.assertNotIn(">", encoded)
        self.assertNotIn("&", encoded)
        self.assertIn("\\u003c/script\\u003e", encoded)
        self.assertIn("\\u2028", encoded)
        self.assertIn("\\u2029", encoded)


class RenderDashboardTests(DashboardTestCase):
    def test_template_contains_exact_tokens_once_and_accessible_offline_views(self):
        template = (SKILL_ROOT / "assets" / "dashboard-template.html").read_text(
            encoding="utf-8"
        )

        self.assertEqual(template.count("__NOVEL_TITLE__"), 1)
        self.assertEqual(template.count("__STORY_DATA__"), 1)
        for required in (
            'id="timeline-view"',
            'id="relationships-view"',
            'id="clues-view"',
            "aria-controls=\"timeline-view\"",
            "aria-controls=\"relationships-view\"",
            "aria-controls=\"clues-view\"",
            "function circularLayout(nodes, width, height, radius)",
            "const centerX = width / 2;",
            "const centerY = height / 2;",
            "const angle = nodes.length === 1 ? 0 : (Math.PI * 2 * index) / nodes.length;",
            "return { ...node, x: centerX + Math.cos(angle) * radius, y: centerY + Math.sin(angle) * radius };",
            "function clueColumn(nodeId)",
            'if (nodeId.startsWith("mystery-")) return 0;',
            'if (nodeId.startsWith("clue-")) return 1;',
            'if (nodeId.startsWith("char-")) return 2;',
            "<ol",
            "<svg",
            "<title>",
            "@media print",
            ":focus-visible",
            'id="relationship-accessible-list"',
            'id="clue-accessible-list"',
            'role="group"',
            "/* PURE_CORE_START */",
            "/* PURE_CORE_END */",
        ):
            self.assertIn(required, template)
        self.assertNotIn('role="img"', template)
        lowered = template.lower()
        for forbidden in (
            "https://",
            "http://",
            "fetch(",
            "xmlhttprequest",
            "<script src=",
            "type=\"module\"",
            "@import",
        ):
            self.assertNotIn(forbidden, lowered)

    def test_render_contains_safe_title_utf8_data_and_all_views(self):
        output = self.project / "visualizations" / "novel-dashboard.html"

        returned = render_dashboard(self.project, output)
        html = output.read_text(encoding="utf-8")

        self.assertEqual(returned, output.resolve())
        self.assertIn('id="timeline-view"', html)
        self.assertIn('id="relationships-view"', html)
        self.assertIn('id="clues-view"', html)
        self.assertIn("林岚", html)
        self.assertIn("&lt;雾城 &amp; &quot;梦&quot;&gt;", html)
        self.assertNotIn('<雾城 & "梦">', html)
        self.assertNotIn("https://", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("</script><script>alert", html)
        self.assertIn("Generated from canonical data:", html)
        self.assertIn('"language":"zh-CN"', html)
        payload = dashboard_payload(html)
        self.assertEqual(
            payload["enabled_views"],
            ["timeline", "relationships", "clues"],
        )

    def test_timeline_only_keeps_participant_characters_without_enabling_relationships(self):
        output = self.project / "visualizations" / "timeline-dashboard.html"

        render_dashboard(self.project, output, types=("timeline",))
        payload = dashboard_payload(output.read_text(encoding="utf-8"))
        story = payload["story"]

        self.assertEqual(payload["enabled_views"], ["timeline"])
        self.assertEqual(
            [record["id"] for record in story["timeline"]["events"]],
            ["event-arrival", "event-secret", "event-mislabelled-plan"],
        )
        self.assertEqual(
            [record["id"] for record in story["relationships"]["characters"]],
            ["char-lan", "char-secret"],
        )
        self.assertEqual(story["relationships"]["relationships"], [])
        self.assertEqual(story["clues"]["mysteries"], [])
        self.assertEqual(story["clues"]["clues"], [])
        self.assertEqual(story["clues"]["links"], [])
        self.assertNotIn("char-wu", story_record_ids(story))

    def test_timeline_only_closes_over_event_to_clue_link_dependencies(self):
        data = event_link_dependency_data()
        for name in ("timeline", "relationships", "clues"):
            write_json(
                self.project / "continuity" / (name + ".json"),
                data[name],
            )

        for mode in ("author", "reader"):
            with self.subTest(mode=mode):
                output = self.project / "visualizations" / (mode + "-timeline.html")
                render_dashboard(
                    self.project,
                    output,
                    mode=mode,
                    types=("timeline",),
                )
                payload = dashboard_payload(output.read_text(encoding="utf-8"))
                story = payload["story"]
                event = story["timeline"]["events"][0]
                dependency_ids = event["causes"] + event["effects"]
                link_ids = {
                    record["id"] for record in story["clues"]["links"]
                }

                self.assertEqual(payload["enabled_views"], ["timeline"])
                self.assertEqual(len(dependency_ids), 2)
                self.assertLessEqual(set(dependency_ids), link_ids)
                self.assertEqual(len(story["clues"]["mysteries"]), 2)
                self.assertEqual(len(story["clues"]["clues"]), 2)
                self.assertLessEqual(
                    story_dependency_ids(story),
                    story_record_ids(story),
                )
                if mode == "reader":
                    serialized = json.dumps(story, ensure_ascii=False)
                    self.assertTrue(
                        all(identifier.startswith("link-reader-") for identifier in dependency_ids)
                    )
                    for secret in (
                        "link-clock-dust",
                        "link-door-fiber",
                        "mystery-clock",
                        "clue-dust",
                        "SECRET",
                    ):
                        self.assertNotIn(secret, serialized)

    def test_relationships_only_keeps_relationships_and_endpoint_characters(self):
        output = self.project / "visualizations" / "relationships-dashboard.html"

        render_dashboard(self.project, output, types=("relationships",))
        payload = dashboard_payload(output.read_text(encoding="utf-8"))
        story = payload["story"]

        self.assertEqual(payload["enabled_views"], ["relationships"])
        self.assertEqual(
            [record["id"] for record in story["relationships"]["characters"]],
            ["char-lan", "char-wu", "char-secret"],
        )
        self.assertEqual(
            [record["id"] for record in story["relationships"]["relationships"]],
            ["rel-lan-wu", "rel-lan-secret"],
        )
        self.assertEqual(story["timeline"]["events"], [])
        self.assertEqual(story["clues"]["mysteries"], [])
        self.assertEqual(story["clues"]["clues"], [])
        self.assertEqual(story["clues"]["links"], [])

    def test_clues_only_keeps_recursive_cross_domain_dependencies_without_overretaining(self):
        data = populated_data()
        data["clues"]["links"].append({
            "id": "link-clock-arrival",
            "source": "mystery-clock",
            "target": "event-arrival",
            "type": "points-to",
            "certainty": "confirmed",
            "visibility": "spoiler-safe",
            "source_refs": ["ch-01#arrival"],
        })
        before = copy.deepcopy(data)

        selected = _select_story_views(data, ("clues",))

        self.assertEqual(data, before)
        self.assertEqual(
            [record["id"] for record in selected["timeline"]["events"]],
            ["event-arrival", "event-secret"],
        )
        self.assertEqual(
            [record["id"] for record in selected["relationships"]["characters"]],
            ["char-lan", "char-wu", "char-secret"],
        )
        self.assertEqual(
            [record["id"] for record in selected["relationships"]["relationships"]],
            ["rel-lan-secret"],
        )
        self.assertEqual(
            [record["id"] for record in selected["clues"]["links"]],
            [
                "link-clock-dust",
                "link-dust-secret",
                "link-mystery-rel",
                "link-door-fiber",
                "link-clock-arrival",
            ],
        )
        self.assertNotIn("event-mislabelled-plan", story_record_ids(selected))
        self.assertNotIn("rel-lan-wu", story_record_ids(selected))
        self.assertLessEqual(story_dependency_ids(selected), story_record_ids(selected))

    def test_timeline_and_clues_dependency_closure_has_no_dangling_ids(self):
        selected = _select_story_views(
            populated_data(),
            ("timeline", "clues"),
        )

        self.assertLessEqual(story_dependency_ids(selected), story_record_ids(selected))
        self.assertEqual(
            [record["id"] for record in selected["relationships"]["relationships"]],
            ["rel-lan-secret"],
        )
        self.assertEqual(
            [record["id"] for record in selected["clues"]["links"]],
            [
                "link-clock-dust",
                "link-dust-secret",
                "link-mystery-rel",
                "link-door-fiber",
            ],
        )
        self.assertNotIn("rel-lan-wu", story_record_ids(selected))

    def test_selected_story_is_a_deep_copy_of_nested_reference_lists(self):
        data = populated_data()
        original = copy.deepcopy(data)

        selected = _select_story_views(data, ("timeline",))
        selected["timeline"]["events"][0]["participants"].append("char-added")
        selected["timeline"]["events"][0]["source_refs"].append("ch-99#changed")

        self.assertEqual(data, original)

    def test_selector_rejects_unknown_and_empty_dependency_ids(self):
        for dependency_id in ("event-missing", ""):
            with self.subTest(dependency_id=dependency_id):
                data = populated_data()
                data["timeline"]["events"][0]["causes"] = [dependency_id]

                with self.assertRaisesRegex(ValueError, "unknown dependency"):
                    _select_story_views(data, ("timeline",))

    def test_reader_render_omits_author_and_author_planned_details(self):
        output = self.project / "visualizations" / "reader-dashboard.html"

        render_dashboard(self.project, output, mode="reader")
        html = output.read_text(encoding="utf-8")

        self.assertIn("林岚", html)
        for secret in (
            "幕后人",
            "幕后真相",
            "只供作者查看",
            "误标计划",
            "尚未公开",
            "SECRET_ALIAS",
            "SECRET_ROLE",
            "SECRET_FACTION",
            "SECRET_NOTES",
            "SECRET_PLANNED_PAYOFF",
            "SECRET_UNRESOLVED_ACTUAL",
            "SECRET_SECOND_PAYOFF",
            "ch-99",
            "char-lan",
            "char-wu",
            "rel-lan-wu",
            "mystery-clock",
            "clue-dust",
            "link-clock-dust",
        ):
            self.assertNotIn(secret, html)
        self.assertNotIn("char-secret", html)
        self.assertNotIn("rel-lan-secret", html)
        self.assertNotIn("link-dust-secret", html)
        self.assertNotRegex(html, r'"generated_at":"\d{4}-\d{2}-\d{2}T')

    def test_template_tokens_in_title_do_not_trigger_recursive_replacement(self):
        config_path = self.project / "novel.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["title"] = "Token __STORY_DATA__ and __NOVEL_TITLE__"
        write_json(config_path, config)
        output = self.project / "visualizations" / "novel-dashboard.html"

        render_dashboard(self.project, output)
        html = output.read_text(encoding="utf-8")

        self.assertIn(
            "<h1>Token __STORY_DATA__ and __NOVEL_TITLE__</h1>",
            html,
        )
        self.assertEqual(html.count("const storyData ="), 1)

    def test_repeated_render_is_byte_stable(self):
        output = self.project / "visualizations" / "novel-dashboard.html"

        render_dashboard(self.project, output)
        first = output.read_bytes()
        render_dashboard(self.project, output)

        self.assertEqual(output.read_bytes(), first)

    def test_invalid_story_data_does_not_replace_old_dashboard(self):
        output = self.project / "visualizations" / "novel-dashboard.html"
        output.write_text("old dashboard", encoding="utf-8")
        broken = copy.deepcopy(self.data["timeline"])
        broken["events"][0]["participants"] = ["char-missing"]
        write_json(self.project / "continuity" / "timeline.json", broken)

        with self.assertRaisesRegex(ValueError, "Invalid story data"):
            render_dashboard(self.project, output)

        self.assertEqual(output.read_text(encoding="utf-8"), "old dashboard")

    def test_invalid_timeline_event_references_do_not_replace_old_dashboard(self):
        cases = (
            ("causes", "event-missing"),
            ("effects", "event-missing"),
            ("causes", ""),
            ("effects", ""),
        )
        output = self.project / "visualizations" / "novel-dashboard.html"

        for field, value in cases:
            for mode in ("author", "reader"):
                with self.subTest(field=field, value=value, mode=mode):
                    output.write_text("old dashboard", encoding="utf-8")
                    broken = copy.deepcopy(self.data["timeline"])
                    broken["events"][0][field] = [value]
                    write_json(self.project / "continuity" / "timeline.json", broken)

                    with self.assertRaisesRegex(ValueError, "Invalid story data"):
                        render_dashboard(self.project, output, mode=mode)

                    self.assertEqual(
                        output.read_text(encoding="utf-8"),
                        "old dashboard",
                    )

    def test_existing_cross_domain_event_references_render_in_both_modes(self):
        output = self.project / "visualizations" / "novel-dashboard.html"
        timeline = copy.deepcopy(self.data["timeline"])
        timeline["events"][0]["causes"] = ["char-lan"]
        write_json(self.project / "continuity" / "timeline.json", timeline)

        for mode in ("author", "reader"):
            with self.subTest(mode=mode):
                render_dashboard(self.project, output, mode=mode)
                self.assertTrue(output.read_text(encoding="utf-8"))

    def test_atomic_publish_failure_preserves_old_dashboard_and_cleans_temp(self):
        output = self.project / "visualizations" / "novel-dashboard.html"
        output.write_text("old dashboard", encoding="utf-8")

        with mock.patch(
            "scripts.render_dashboard.os.replace",
            side_effect=OSError("publish failed"),
        ):
            with self.assertRaisesRegex(OSError, "publish failed"):
                render_dashboard(self.project, output)

        self.assertEqual(output.read_text(encoding="utf-8"), "old dashboard")
        self.assertEqual(list(output.parent.glob(".novel-dashboard.html.*.tmp")), [])

    def test_symlink_output_is_rejected_without_touching_target(self):
        sensitive = Path(self.temporary_directory.name) / "sensitive.txt"
        sensitive.write_text("keep me", encoding="utf-8")
        output = self.project / "visualizations" / "novel-dashboard.html"
        output.symlink_to(sensitive)

        with self.assertRaisesRegex(ValueError, "symlink"):
            render_dashboard(self.project, output)

        self.assertEqual(sensitive.read_text(encoding="utf-8"), "keep me")

    def test_directory_swap_between_check_and_publish_cannot_write_external(self):
        output = self.project / "visualizations" / "novel-dashboard.html"
        external = Path(self.temporary_directory.name) / "external"
        external.mkdir()
        sensitive = external / output.name
        sensitive.write_text("keep me", encoding="utf-8")
        moved = self.project / "visualizations-original"
        from scripts import render_dashboard as dashboard_module

        original_atomic_write = dashboard_module._atomic_write_text

        def swap_then_write(*arguments, **keywords):
            output.parent.rename(moved)
            output.parent.symlink_to(external, target_is_directory=True)
            return original_atomic_write(*arguments, **keywords)

        with mock.patch(
            "scripts.render_dashboard._atomic_write_text",
            side_effect=swap_then_write,
        ):
            with self.assertRaises(OSError):
                render_dashboard(self.project, output)

        self.assertEqual(sensitive.read_text(encoding="utf-8"), "keep me")

    def test_python_sources_parse_as_python_39(self):
        for relative_path in ("scripts/render_dashboard.py", "scripts/story_data.py"):
            source = (SKILL_ROOT / relative_path).read_text(encoding="utf-8")
            ast.parse(source, filename=relative_path, feature_version=(3, 9))


class CommandLineTests(DashboardTestCase):
    def run_cli(self, *arguments):
        return subprocess.run(
            [sys.executable, "scripts/render_dashboard.py", *map(str, arguments)],
            cwd=SKILL_ROOT,
            capture_output=True,
            text=True,
        )

    def test_cli_uses_author_default_path_and_prints_resolved_path(self):
        result = self.run_cli(self.project)
        expected = (self.project / "visualizations" / "novel-dashboard.html").resolve()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(expected))
        self.assertTrue(expected.is_file())

    def test_cli_reader_mode_uses_separate_default_path(self):
        result = self.run_cli(self.project, "--mode", "reader")
        expected = (self.project / "visualizations" / "reader-dashboard.html").resolve()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(expected))
        self.assertTrue(expected.is_file())

    def test_choice_one_cli_types_command_enables_all_three_views(self):
        result = self.run_cli(
            self.project,
            "--types",
            "timeline,relationships,clues",
            "--mode",
            "author",
        )
        output = self.project / "visualizations" / "novel-dashboard.html"

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = dashboard_payload(output.read_text(encoding="utf-8"))
        self.assertEqual(
            payload["enabled_views"],
            ["timeline", "relationships", "clues"],
        )

    def test_choice_three_cli_keeps_only_reader_dependency_closure(self):
        result = self.run_cli(
            self.project,
            "--types",
            "timeline,clues",
            "--mode",
            "reader",
        )
        output = self.project / "visualizations" / "reader-dashboard.html"

        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = output.read_text(encoding="utf-8")
        payload = dashboard_payload(rendered)
        self.assertEqual(payload["enabled_views"], ["timeline", "clues"])
        self.assertEqual(
            [
                record["id"]
                for record in payload["story"]["relationships"]["characters"]
            ],
            ["char-reader-001", "char-reader-002"],
        )
        self.assertEqual(payload["story"]["relationships"]["relationships"], [])
        self.assertLessEqual(
            story_dependency_ids(payload["story"]),
            story_record_ids(payload["story"]),
        )
        self.assertTrue(
            all(
                record["id"].startswith("char-reader-")
                for record in payload["story"]["relationships"]["characters"]
            )
        )
        for relationship_secret in (
            "SECRET_NOTES",
            "共同调查",
            "尚未公开",
        ):
            self.assertNotIn(relationship_secret, rendered)

    def test_cli_rejects_unknown_empty_and_duplicate_types_clearly(self):
        for value, expected in (
            ("timeline,unknown", "unknown dashboard type"),
            ("", "at least one dashboard type"),
            ("timeline,timeline", "duplicate dashboard type"),
        ):
            with self.subTest(value=value):
                result = self.run_cli(self.project, "--types", value)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ERROR:", result.stderr)
                self.assertIn(expected, result.stderr)
                self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_programmatic_renderer_rejects_empty_types(self):
        output = self.project / "visualizations" / "novel-dashboard.html"

        with self.assertRaisesRegex(ValueError, "at least one dashboard type"):
            render_dashboard(self.project, output, types=[])

    def test_cli_explicit_output_may_be_outside_visualizations(self):
        output = self.project / "exports" / "dashboard.html"
        output.parent.mkdir()

        result = self.run_cli(self.project, "--output", output)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(output.is_file())

    def test_cli_explicit_output_rejects_symlink_parent(self):
        sensitive_directory = Path(self.temporary_directory.name) / "sensitive"
        sensitive_directory.mkdir()
        sensitive = sensitive_directory / "dashboard.html"
        sensitive.write_text("keep me", encoding="utf-8")
        linked_directory = self.project / "exports"
        linked_directory.symlink_to(sensitive_directory, target_is_directory=True)

        result = self.run_cli(
            self.project,
            "--output",
            linked_directory / "dashboard.html",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(sensitive.read_text(encoding="utf-8"), "keep me")

    def test_cli_error_is_clear_nonzero_without_traceback(self):
        (self.project / "novel.json").write_text("not json", encoding="utf-8")

        result = self.run_cli(self.project)
        combined = result.stdout + result.stderr

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERROR:", combined)
        self.assertNotIn("Traceback", combined)


@unittest.skipUnless(shutil.which("node"), "Node.js is not available")
class DashboardJavaScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        template = (SKILL_ROOT / "assets" / "dashboard-template.html").read_text(
            encoding="utf-8"
        )
        cls.script = template.split("<script>", 1)[1].rsplit("</script>", 1)[0]
        cls.core = cls.script.split("/* PURE_CORE_START */", 1)[1].split(
            "/* PURE_CORE_END */", 1
        )[0]

    def run_core(self, expression, payload):
        program = (
            self.core
            + "\nconst fs = require('fs');"
            + "\nconst input = JSON.parse(fs.readFileSync(0, 'utf8'));"
            + "\nprocess.stdout.write(JSON.stringify("
            + expression
            + "));"
        )
        result = subprocess.run(
            ["node", "-e", program],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_embedded_javascript_has_valid_node_syntax(self):
        result = subprocess.run(
            ["node", "--check", "-"],
            input=self.script,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_clue_model_keeps_relationship_endpoint_and_edge(self):
        model = self.run_core(
            "buildClueGraphModel(input.story, input.filters)",
            {
                "story": populated_data(),
                "filters": {
                    "mystery": "mystery-clock",
                    "status": "",
                    "knownBy": "",
                    "unresolvedOnly": False,
                },
            },
        )
        self.assertIn("rel-lan-secret", [node["id"] for node in model["nodes"]])
        self.assertIn("link-mystery-rel", [link["id"] for link in model["links"]])

    def test_clue_model_mystery_filter_returns_only_induced_component(self):
        model = self.run_core(
            "buildClueGraphModel(input.story, input.filters)",
            {
                "story": populated_data(),
                "filters": {
                    "mystery": "mystery-door",
                    "status": "",
                    "knownBy": "",
                    "unresolvedOnly": False,
                },
            },
        )
        node_ids = [node["id"] for node in model["nodes"]]
        self.assertEqual(node_ids, ["clue-fiber", "mystery-door"])
        self.assertEqual([link["id"] for link in model["links"]], ["link-door-fiber"])

    def test_keyboard_activation_handles_enter_and_space_only(self):
        expression = """(() => {
          let calls = 0;
          let prevented = 0;
          const event = { key: input.key, preventDefault() { prevented += 1; } };
          const handled = activateOnKeyboard(event, () => { calls += 1; });
          return { handled, calls, prevented };
        })()"""
        for key in ("Enter", " "):
            self.assertEqual(
                self.run_core(expression, {"key": key}),
                {"handled": True, "calls": 1, "prevented": 1},
            )
        self.assertEqual(
            self.run_core(expression, {"key": "ArrowDown"}),
            {"handled": False, "calls": 0, "prevented": 0},
        )

    def test_dynamic_geometry_contains_many_long_chinese_labels(self):
        nodes = [
            {
                "id": "clue-item-%02d" % index,
                "title": "非常长的中文线索标题用于验证不会裁剪%02d" % index,
            }
            for index in range(12)
        ]
        layout = self.run_core("clueGraphLayout(input.nodes)", {"nodes": nodes})
        self.assertGreater(layout["height"], 520)
        self.assertTrue(
            all(node["y"] + 30 <= layout["height"] for node in layout["nodes"])
        )
        shortened = self.run_core(
            "shortLabel(input.label, 12)",
            {"label": "这是一个特别特别长的中文图形节点标题"},
        )
        self.assertLessEqual(len(shortened), 12)

        relationship = self.run_core(
            "relationshipGraphGeometry(input.count)",
            {"count": 40},
        )
        self.assertGreater(relationship["height"], 520)


if __name__ == "__main__":
    unittest.main()
