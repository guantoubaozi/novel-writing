"""Create a new novel project from the bundled template."""

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "project-template"


def _is_template_destination(destination: Path, template_root: Path) -> bool:
    return destination == template_root or template_root in destination.parents


def initialize_project(destination: Path, title: str, language: str = "zh-CN") -> Path:
    """Initialize an empty project directory and return its resolved path."""
    destination = destination.resolve()
    template_root = TEMPLATE_ROOT.resolve()
    if _is_template_destination(destination, template_root):
        raise ValueError(f"Refusing to create a project inside the template: {destination}")
    if destination.exists() and (
        not destination.is_dir() or any(destination.iterdir())
    ):
        raise FileExistsError(f"Refusing to overwrite nonempty directory: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=".novel-writing-", dir=str(destination.parent))
    )
    try:
        shutil.copytree(template_root, staging, dirs_exist_ok=True)
        snapshots = staging / "visualizations" / "snapshots"
        snapshots.mkdir(parents=True, exist_ok=True)

        config_path = staging / "novel.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["title"] = title
        config["language"] = language
        config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        staging.replace(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize a novel project.")
    parser.add_argument("project_dir", metavar="PROJECT_DIR", type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--language", default="zh-CN")
    arguments = parser.parse_args()

    try:
        project_path = initialize_project(
            arguments.project_dir,
            arguments.title,
            arguments.language,
        )
    except (FileExistsError, OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1

    print(project_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
