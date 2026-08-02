# Novel Writing

> A long-form fiction Skill that keeps inference out of canon, respects character knowledge boundaries, and supports the full path from premise to reviewed chapters and story visualizations.

[中文说明](README.md) · [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

## What it does

Novel Writing organizes fiction writing as an author-controlled project rather than a one-shot prose prompt. It supports premise development, plotting, character arcs, chapter drafting, six-dimensional review, continuity auditing, safe structured-state updates, and offline visualizations.

Its central rule is simple: AI suggestions are not canon. Story information remains separated as:

- `confirmed`: canon explicitly accepted by the author.
- `inferred`: conclusions derived from the text but not yet confirmed.
- `author-planned`: future events or secrets the author intends to use.

## Workflow

```text
Premise and boundaries
    → master outline and character arcs
    → author-selected chapter boundary
    → relevant project context and continuity
    → draft chapter
    → six-dimensional review and author curation
    → candidate state preview and explicit confirmation
    → timeline, relationship, and clue visualizations
    → next chapter until the manuscript is complete
```

The order matters: author intent is resolved before drafting, prose is reviewed before canon changes, contradictions are reported before repair, and visualizations are generated only from confirmed structured state.

## Highlights

- Complete novel workflow with no limits on chapters, characters, reviews, or dashboards.
- Fine-grained continuity across chronology, location, physical state, inventory, knowledge, relationships, point of view, and unresolved promises.
- Manual review, AI review with human curation, and one-round AI review-and-revision with human curation.
- Author and spoiler-safe reader dashboards for timelines, relationships, mysteries, and clues.
- Digest-bound confirmation, validation, atomic publishing, and path-safety protections for structured data.
- 100 automated tests covering the data model, CLI, reader redaction, safe publishing, and end-to-end behavior.

## Installation

Python 3.9 or later is required. Runtime scripts use only the Python standard library.

```bash
git clone https://github.com/guantoubaozi/novel-writing.git
cp -R novel-writing ~/.codex/skills/novel-writing
```

Then start with:

```text
Use $novel-writing to create a new novel project.
```

## Quick start

```bash
python3 scripts/init_project.py ~/Documents/my-novel \
  --title "Letters from Mist Harbor" \
  --language en
```

Ask the agent to create the premise and outline, draft the author-selected next chapter, run `/novel:review`, and then use `/novel:visualize` to preview and confirm structured story changes.

## Free edition boundary

This repository supports writing a complete novel. It intentionally excludes automatic whole-book chapter decomposition, automatic multi-scene generation batches, advanced context compression and relevance assembly, cache freshness management, and automated tiered session handoff generation. Chapter boundaries remain author-controlled.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## License

[MIT](LICENSE). Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).
