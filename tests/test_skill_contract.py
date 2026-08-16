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

    def test_description_states_capability_and_trigger_context(self):
        content = self.read("SKILL.md")
        match = re.match(r"^---\n(?P<frontmatter>.*?)\n---", content, flags=re.DOTALL)
        self.assertIsNotNone(match)
        description = next(
            line.split(":", 1)[1].strip()
            for line in match.group("frontmatter").splitlines()
            if line.startswith("description:")
        )
        self.assertIn("Plan, draft, review, revise, audit, and visualize", description)
        self.assertIn("Use when an author provides", description)
        self.assertIn("novel idea", description)
        self.assertIn("chapter draft", description)

    def test_writer_facing_intro_is_concise_and_readme_is_complete(self):
        skill = self.read("SKILL.md")
        readme = self.read("README.md")
        intro = re.search(
            r"^## For writers\n(?P<body>.*?)(?=^## Core workflow)",
            skill,
            flags=re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(intro)
        self.assertLessEqual(len(intro.group("body").split()), 90)
        for phrase in (
            "not a one-click novel generator",
            "author keeps control",
            "from a rough idea to a complete long-form manuscript",
        ):
            self.assertIn(phrase, intro.group("body"))
        for heading in (
            "## What it can help you do",
            "## An author-led way to collaborate",
            "## Who it is for",
            "## Ways to begin",
            "## Common operations",
        ):
            self.assertIn(heading, readme)
        for phrase in (
            "memory trading",
            "chapter seven",
            "You do not need a complete outline",
        ):
            self.assertIn(phrase, readme)

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

    def test_character_context_uses_three_layers_and_staged_checks(self):
        skill = self.read("SKILL.md")
        workflow = self.read("references/project-workflow.md")
        character_context = self.read("references/character-context.md")
        chapter_plan = self.read("assets/project-template/outline/chapter-plan.md")
        lowered = character_context.lower()
        for phrase in (
            "canonical character dossier",
            "chapter character card",
            "ephemeral scene profile",
        ):
            self.assertIn(phrase, lowered)
        self.assertIn("Character ID", chapter_plan)
        self.assertIn("pre-draft hard constraints", lowered)
        self.assertIn("detail consistency", lowered)
        self.assertIn("character-context.md", skill)
        self.assertIn("Do not load complete `continuity/*` records by default", workflow)

    def test_optional_eight_beat_lens_is_flexible_and_used_in_review(self):
        plotting = self.read("references/plotting.md")
        questioning = self.read("references/questioning.md")
        review = self.read("references/chapter-review.md")
        master_outline = self.read("assets/project-template/outline/master-outline.md")
        chapter_plan = self.read("assets/project-template/outline/chapter-plan.md")

        self.assertIn("Optional eight-beat lens", plotting)
        beats = (
            "Goal",
            "Opportunity",
            "Obstacle",
            "Response",
            "Disruption",
            "Reinterpretation",
            "Decision",
            "New state",
        )
        positions = [plotting.index("**" + beat + ":") for beat in beats]
        self.assertEqual(positions, sorted(positions))
        for phrase in (
            "merge adjacent functions",
            "span chapters",
            "not applicable",
            "Do not invent",
            "counterattack",
            "hook",
        ):
            self.assertIn(phrase, plotting)
        for phrase in (
            "opportunity from guaranteed success",
            "disruption changes the situation",
            "reinterpretation changes its meaning",
            "decision need not be a counterattack",
        ):
            self.assertIn(phrase, questioning)
        for template in (master_outline, chapter_plan):
            self.assertIn("Optional Eight-Beat", template)
            self.assertIn("may merge", template)
            self.assertIn("span chapters", template)
        for phrase in (
            "Optional eight-beat structural diagnostic",
            "missing named beat is not a finding",
            "not applicable",
            "passive causality",
            "unsupported reinterpretation",
            "forced hook",
            "quiet aftermath",
            "temporary closure",
        ):
            self.assertIn(phrase, review)

    def test_referenced_local_files_exist(self):
        skill = self.read("SKILL.md")
        references = re.findall(r"\]\((references/[^)]+)\)", skill)
        scripts = re.findall(r"`(scripts/[^` ]+\.py)", skill)
        for relative_path in set(references + scripts):
            self.assertTrue((SKILL_ROOT / relative_path).is_file(), relative_path)


if __name__ == "__main__":
    unittest.main()
