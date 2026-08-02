import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from scripts import init_project
from scripts.init_project import initialize_project


class InitProjectTests(unittest.TestCase):
    def test_initializes_complete_project(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "归途"
            initialize_project(target, "归途")
            config = json.loads((target / "novel.json").read_text(encoding="utf-8"))
            self.assertEqual(config["title"], "归途")
            self.assertEqual(config["schema_version"], 1)
            self.assertTrue((target / "continuity" / "timeline.json").is_file())
            self.assertTrue((target / "visualizations" / "snapshots").is_dir())

    def test_refuses_nonempty_destination(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "existing"
            target.mkdir()
            (target / "chapter.md").write_text("user text", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                initialize_project(target, "Existing")
            self.assertEqual((target / "chapter.md").read_text(encoding="utf-8"), "user text")

    def test_initializes_existing_empty_destination(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "empty"
            target.mkdir()
            self.assertEqual(initialize_project(target, "Empty"), target.resolve())
            self.assertEqual(
                json.loads((target / "novel.json").read_text(encoding="utf-8"))["title"],
                "Empty",
            )

    def test_refuses_destination_nested_in_template_before_copying(self):
        with TemporaryDirectory() as directory:
            template_root = Path(directory) / "template"
            target = template_root / "generated"
            with mock.patch.object(init_project, "TEMPLATE_ROOT", template_root):
                with mock.patch.object(init_project.shutil, "copytree") as copytree:
                    with self.assertRaises(ValueError):
                        initialize_project(target, "Nested")
            copytree.assert_not_called()
            self.assertFalse(target.exists())

    def test_copy_failure_leaves_no_project_or_staging_directory(self):
        with TemporaryDirectory() as directory:
            parent = Path(directory)
            target = parent / "failed"
            with mock.patch.object(
                init_project.shutil,
                "copytree",
                side_effect=OSError("copy failed"),
            ):
                with self.assertRaises(OSError):
                    initialize_project(target, "Failed")
            self.assertFalse(target.exists())
            self.assertEqual(list(parent.glob(".novel-writing-*")), [])

    def test_configuration_failure_leaves_no_project_or_staging_directory(self):
        with TemporaryDirectory() as directory:
            parent = Path(directory)
            target = parent / "failed"
            with mock.patch.object(Path, "write_text", side_effect=OSError("write failed")):
                with self.assertRaises(OSError):
                    initialize_project(target, "Failed")
            self.assertFalse(target.exists())
            self.assertEqual(list(parent.glob(".novel-writing-*")), [])

    def test_publish_race_does_not_overwrite_user_file(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "raced"

            def copy_then_create_user_file(source, staging, *args, **kwargs):
                (staging / "novel.json").write_text("{}", encoding="utf-8")
                target.mkdir(exist_ok=True)
                (target / "novel.json").write_text("user text", encoding="utf-8")

            with mock.patch.object(
                init_project.shutil,
                "copytree",
                side_effect=copy_then_create_user_file,
            ):
                with self.assertRaises(OSError):
                    initialize_project(target, "Raced")
            self.assertEqual((target / "novel.json").read_text(encoding="utf-8"), "user text")


if __name__ == "__main__":
    unittest.main()
