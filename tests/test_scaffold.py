from pathlib import Path
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]


class ScaffoldTests(unittest.TestCase):
    def test_required_directories_exist(self):
        for relative_path in ("agents", "assets", "references", "scripts", "tests"):
            self.assertTrue((SKILL_ROOT / relative_path).is_dir(), relative_path)

    def test_metadata_mentions_free_skill(self):
        metadata = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "Novel Writing"', metadata)
        self.assertIn("$novel-writing", metadata)

    def test_paid_only_components_are_absent(self):
        for relative_path in (
            "scripts/build_context.py",
            "scripts/write_session_handoff.py",
            "references/session-handoff.md",
        ):
            self.assertFalse((SKILL_ROOT / relative_path).exists(), relative_path)

    def test_character_dossier_template_exists(self):
        template = SKILL_ROOT / "assets" / "project-template" / "characters" / "character-template.md"
        self.assertTrue(template.is_file())
        content = template.read_text(encoding="utf-8")
        self.assertIn("## Stable Core", content)
        self.assertIn("## Voice and Embodiment", content)


if __name__ == "__main__":
    unittest.main()
