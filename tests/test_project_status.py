import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.project_status import build_status


class ProjectStatusTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.project = Path(self.tempdir.name)
        self.write("novel.json", json.dumps({"title": "Test Novel"}))
        self.write("chapters/chapter-001.md", "他回家了。")
        self.write("chapters/chapter-002.md", "He went home.")
        self.write("chapters/index.md", "ignored")
        self.write("continuity/timeline.json", json.dumps({"schema_version": 1, "events": []}))
        self.write("continuity/clues.json", json.dumps({"schema_version": 1,
            "mysteries": [
                {"id": "mystery-open", "status": "open"},
                {"id": "mystery-closed", "status": "resolved"},
            ],
            "clues": [
                {"id": "clue-open", "status": "seeded"},
                {"id": "clue-done", "status": "resolved"},
            ], "links": []
        }))
        self.write("continuity/relationships.json", json.dumps({"schema_version": 1,
            "characters": [], "relationships": [
                {"id": "rel-active", "status": "active"},
                {"id": "rel-ended", "status": "ended"},
            ]
        }))

    def tearDown(self):
        self.tempdir.cleanup()

    def write(self, relative, content):
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_reports_chapter_text_and_continuity_counts(self):
        self.assertEqual(build_status(self.project), {
            "chapters": 2,
            "text_units": 7,
            "open_mysteries": 1,
            "unresolved_clues": 1,
            "active_relationships": 1,
        })

    def test_malformed_canonical_collection_fails_clearly(self):
        self.write("continuity/clues.json", json.dumps({"schema_version": 1, "mysteries": [], "clues": {}, "links": []}))
        with self.assertRaisesRegex(ValueError, "clues.clues must be a list"):
            build_status(self.project)
