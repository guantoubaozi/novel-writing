# Letters from Mist Harbor Demo

This minimal project demonstrates how Novel Writing organizes a long-form fiction project:

- `story-bible.md` stores the core premise, themes, and creative boundaries.
- `outline/` stores the overall structure and author-maintained chapter boundaries.
- `characters/` and `style/` store character knowledge limits and narrative voice.
- `chapters/chapter-001.md` provides an example chapter with referenceable anchors.
- `continuity/` stores author-confirmed structured story state.
- `visualizations/` contains author and spoiler-safe reader dashboards.

Show project status:

```bash
python3 ../../scripts/project_status.py .
```

Regenerate the author dashboard:

```bash
python3 ../../scripts/render_dashboard.py . --mode author
```
