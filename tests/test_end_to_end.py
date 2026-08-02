import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.init_project import initialize_project
from scripts.merge_story_updates import merge_update_packet
from scripts.project_status import build_status
from scripts.render_dashboard import render_dashboard
from scripts.story_data import DATA_FILES, atomic_write_json, load_story_data, validate_story_data


SKILL_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = SKILL_ROOT / "tests" / "fixtures" / "chapter-001-update.json"


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.project = initialize_project(
            Path(self.temporary_directory.name) / "project",
            "雾港来信",
        )

    def test_complete_free_project_data_and_visualization_workflow(self):
        chapter = self.project / "chapters" / "chapter-001.md"
        chapter.write_text("# 第一章：旧港\n\n林在清晨抵达旧港。\n", encoding="utf-8")
        packet = json.loads(FIXTURE.read_text(encoding="utf-8"))
        merged, summary = merge_update_packet(load_story_data(self.project), packet)
        for domain, relative_path in DATA_FILES.items():
            atomic_write_json(self.project / relative_path, merged[domain])

        self.assertEqual(validate_story_data(load_story_data(self.project)), [])
        self.assertEqual(summary["events_added"], 1)
        status = build_status(self.project)
        self.assertEqual(status["chapters"], 1)
        self.assertEqual(status["open_mysteries"], 1)

        author_path = render_dashboard(
            self.project,
            self.project / "visualizations" / "novel-dashboard.html",
            "author",
        )
        reader_path = render_dashboard(
            self.project,
            self.project / "visualizations" / "reader-dashboard.html",
            "reader",
        )
        self.assertIn("黄铜钥匙", author_path.read_text(encoding="utf-8"))
        self.assertNotIn("黄铜钥匙", reader_path.read_text(encoding="utf-8"))

    def test_update_fixture_has_stable_digest(self):
        digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        self.assertEqual(len(digest), 64)


if __name__ == "__main__":
    unittest.main()
