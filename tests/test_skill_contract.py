from pathlib import Path
import re
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]


class SkillContractTests(unittest.TestCase):
    def read(self, relative_path):
        return (SKILL_ROOT / relative_path).read_text(encoding="utf-8")

    def test_frontmatter_uses_only_required_fields(self):
        content = self.read("SKILL.md")
        match = re.match(r"^---\n(.*?)\n---", content, flags=re.DOTALL)
        self.assertIsNotNone(match)
        keys = {
            line.split(":", 1)[0]
            for line in match.group(1).splitlines()
            if ":" in line
        }
        self.assertEqual(keys, {"name", "description"})

    def test_free_workflow_covers_complete_novel_cycle(self):
        skill = self.read("SKILL.md")
        for operation in (
            "/novel:new",
            "/novel:outline",
            "/novel:chapter",
            "/novel:review",
            "/novel:revise",
            "/novel:audit",
            "/novel:visualize",
            "/novel:status",
        ):
            self.assertIn(operation, skill)
        self.assertIn("until the manuscript is complete", skill)

    def test_review_and_visualization_are_full_free_features(self):
        skill = self.read("SKILL.md")
        review = self.read("references/chapter-review.md")
        visualization = self.read("references/visualization-workflow.md")
        for choice in (
            "manual review only",
            "auto review with human curation",
            "auto review and auto-revise with human curation",
        ):
            self.assertIn(choice, review)
        for choice in (
            "update all and regenerate HTML",
            "update structured data only",
            "select visualizations",
            "preview candidate changes",
            "skip this chapter",
        ):
            self.assertIn(choice, visualization)
        self.assertIn("chapter-review.md", skill)
        self.assertIn("visualization-workflow.md", skill)

    def test_author_authority_is_explicit(self):
        skill = self.read("SKILL.md")
        for phrase in (
            "confirmed",
            "inferred",
            "author-planned",
            "Never silently overwrite",
            "explicit author confirmation",
        ):
            self.assertIn(phrase, skill)

    def test_free_boundary_is_explicit(self):
        workflow = self.read("references/project-workflow.md")
        self.assertIn("author-controlled", workflow)
        self.assertIn("Do not automatically split the whole outline into chapters", workflow)
        self.assertIn("Do not automatically divide a long chapter", workflow)

    def test_referenced_local_files_exist(self):
        skill = self.read("SKILL.md")
        references = re.findall(r"\]\((references/[^)]+)\)", skill)
        scripts = re.findall(r"`(scripts/[^` ]+\.py)", skill)
        for relative_path in set(references + scripts):
            self.assertTrue((SKILL_ROOT / relative_path).is_file(), relative_path)


if __name__ == "__main__":
    unittest.main()
