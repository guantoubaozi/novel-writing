# Free Project Workflow

## Project files

Use the project scaffold created by `scripts/init_project.py`:

- `novel.json`: title, language, genre, length, viewpoint, tense, and status.
- `story-bible.md`: premise, theme, rules, and author boundaries.
- `outline/master-outline.md`: whole-story causal structure and ending direction.
- `outline/chapter-plan.md`: chapter boundaries chosen and maintained by the author.
- `characters/`, `world/`, and `style/`: active character, setting, and voice material.
- `chapters/`: accepted chapter drafts and a human-readable index.
- `continuity/`: facts, open threads, timeline, relationships, mysteries, and clues.
- `research/`: project-specific research cards and sources.
- `visualizations/`: generated author or reader dashboards.

## Load the working set

Before outlining, drafting, reviewing, or revising, discover relevant authority by searching the project for the target chapter, active character names, decisive facts, and open threads. Then read the smallest complete working set that preserves accuracy:

1. `novel.json` and `style/voice.md`.
2. The relevant sections of `story-bible.md` and `outline/master-outline.md`.
3. The selected entry in `outline/chapter-plan.md`.
4. Relevant character and world sections.
5. The complete `continuity/*` records when continuity can affect the task.
6. The immediately previous chapter in full.
7. Research cards that materially constrain the selected chapter.

Use exact Markdown sections when a full file is unnecessary. Do not load the whole manuscript, superseded revisions, generated HTML, unrelated research, or the prior chat transcript by default.

If two sources disagree, report the conflict before drafting. Do not silently choose the newest, longest, or most detailed version. Ask the author which source governs when authority cannot be established.

## Maintain chapter boundaries

The free workflow supports an entire novel one chapter at a time, but chapter boundaries remain author-controlled:

1. Define or confirm the next chapter in `outline/chapter-plan.md`.
2. Record its entry condition, viewpoint goal, complications, turn, outcome, and exit pressure.
3. Draft the selected chapter as one author-directed operation.
4. Save and review the chapter before moving to the next one.
5. Update the chapter index and confirmed continuity only after author approval.

Do not automatically split the whole outline into chapters. Do not automatically divide a long chapter into a two-to-four-scene generation pipeline. The author may still request individual scenes or continuations explicitly.

## Complete the book

Repeat the chapter cycle until the manuscript is complete. Then:

1. Run a whole-project continuity review.
2. Revisit structure, scene necessity, character agency, pacing, viewpoint, dialogue, imagery, prose, and final continuity in that order.
3. Resolve open threads and intended mysteries.
4. Generate final author visualizations and, when requested, a spoiler-safe reader dashboard.
5. Preserve every pre-revision manuscript version unless the author explicitly authorizes replacement.
