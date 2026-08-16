# Novel Writing

> An author-controlled Agent Skill for planning, drafting, reviewing, revising, auditing, and visualizing complete long-form fiction projects.

![Novel Writing social preview](assets/social-preview.png)

[Chinese README](README_CN.md) · [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

## For writers

From a rough idea to characters, outlines, chapters, and a complete long-form manuscript, Novel Writing helps you develop the story one deliberate step at a time.

This is not a one-click novel generator. It is a writing partner that understands the demands of long-form fiction: it keeps track of relationships, clues, confirmed facts, and planned secrets; helps solve concrete problems in conception, structure, drafting, and revision; and leaves the author's voice and decisions in the author's hands.

## What it can help you do

### Develop an idea into a story

You can begin with a single-sentence premise, a character note, an unfinished outline, or a scene that has stopped working. The skill helps identify:

- The story's central conflict and dramatic question.
- What the protagonist wants and what resists that pursuit.
- How characters may grow, decline, awaken, or fail to change.
- Whether major events form a causal chain rather than a sequence of coincidences.
- Which secrets, mysteries, relationships, and promises deserve development.

It asks questions anchored in the material you supplied instead of rushing to make creative decisions for you.

### Plan outlines and character arcs

Use it to design a complete novel or to solve only the part currently blocking you. It can help:

- Shape beginnings, escalation, reversals, climax, and resolution.
- Adjust pacing and conflict pressure.
- Build character arcs from desire, contradiction, boundaries, and consequential choices.
- Check whether actions remain credible for the established character.
- Arrange foreshadowing, secrets, misunderstandings, clues, and reveals.
- Turn scattered ideas into an actionable chapter plan.
- Optionally use a flexible eight-beat lens without forcing every novel or chapter into the same formula.

An outline remains a working plan, not an unchangeable contract. Confirmed manuscript facts stay separate from interpretations and future possibilities.

### Draft selected chapters

When you are ready to write prose, the skill uses the confirmed story state, active character context, voice guidance, and chapter purpose to help draft the chapter you selected. It pays attention to:

- Concrete scene goals, resistance, turns, and consequences.
- Conflict dramatized through action and dialogue.
- Distinct character voices and knowledge boundaries.
- Emotion rendered through body, behavior, perception, and selective interiority.
- Viewpoint access and narrative clarity.
- Endings that create appropriate forward pressure or meaningful aftermath.
- Consistency with the project's established voice.

The free workflow keeps chapter boundaries author-maintained, so the system does not silently partition the whole book or take over the writing sequence.

### Review and revise

Submit a passage or completed chapter, or name a specific difficulty. The skill can:

- Find pacing that drags, rushes, or skips the scene readers need to witness.
- Strengthen underdeveloped dramatic moments.
- Improve dialogue, action, emotional expression, and viewpoint clarity.
- Reduce excessive explanation, information dumps, vague abstraction, and forced thematic conclusions.
- Check motivation, character focus, continuity, foreshadowing subtlety, and prose clarity.
- Preserve the source and present proposed revisions for human curation.

It never needs to silently overwrite the manuscript. You can inspect suggestions and decide which changes to accept.

### Protect long-form continuity

As a manuscript grows, it becomes easy to lose track of chronology, location, injuries, possessions, information, relationships, and promises. The skill checks:

- Whether character facts remain consistent.
- Whether travel, recovery, and event order remain plausible.
- Whether a character knows something they were never shown or told.
- Whether clues and promises receive fair setup and payoff.
- Whether secrets leak before their intended reveal.
- Whether relationship changes have sufficient cause and aftermath.
- Whether new chapters contradict established story state.

When it finds a conflict, it reports the evidence before proposing a repair instead of deciding which version is canon.

## An author-led way to collaborate

### The author controls canon

Story information remains separated into three states:

- `confirmed`: facts explicitly accepted as canon.
- `inferred`: interpretations supported by the manuscript but not confirmed.
- `author-planned`: future events, secrets, or reveals that remain plans.

An inference never becomes canon merely because the AI suggested it, and an unrevealed plan is not treated as something characters already know.

### The author keeps their voice

The goal is not to impose a uniform AI voice. You can provide a voice guide or ask for qualities such as restraint, sharpness, warmth, stronger imagery, greater intimacy, or more narrative distance. The workflow preserves craft traits rather than imitating a living author's protected style.

### The original remains safe

Brainstorming, summaries, review findings, and candidate prose remain non-final until accepted. Manuscript and structured story files are not silently overwritten.

## Who it is for

This skill works for first-time novelists and experienced writers managing a long project. It is especially useful if you:

- Have an idea but do not know how to develop it into a complete story.
- Are stuck midway through a manuscript and need to recover direction.
- Struggle to keep character behavior, pacing, or plot structure coherent.
- Are writing a long novel with many characters, relationships, or clues.
- Want specific revision guidance rather than a generic evaluation.
- Want AI assistance without surrendering control of the work.

## Ways to begin

- “I have a story idea about memory trading. Help me develop it into a novel.”
- “Here are my character notes. Find the central conflict with the most potential.”
- “Help me design the major character arcs.”
- “I am stuck on chapter seven. The protagonist must leave home, but the motivation is not strong enough.”
- “Using the current outline, help me draft chapter three.”
- “Review this chapter's pacing, motivation, dialogue, and eight-beat progression without forcing every beat to appear.”
- “Check the first ten chapters for timeline or character contradictions.”
- “Keep my voice, but make this confrontation feel more immediate.”

You do not need a complete outline or any technical command knowledge. Bring a premise, a passage, a character, or a concrete writing problem.

## Common operations

| Operation | Purpose |
| --- | --- |
| `/novel:new` | Start a new novel project |
| `/novel:outline` | Design or revise the story outline |
| `/novel:chapter` | Draft an author-selected chapter |
| `/novel:review` | Review a completed chapter |
| `/novel:revise` | Revise existing prose |
| `/novel:audit` | Check continuity and structured story state |
| `/novel:visualize` | Preview and render story visualizations |
| `/novel:status` | Review current manuscript progress |
| `/novel:style-import` | Import a high-level, permission-aware reference style baseline |

## What problem does it solve?

Many fiction tools are good at generating a passage immediately. The harder problem in a long novel is preserving coherence at chapter 20, 50, or 100: characters must still behave like themselves, secrets must not leak early, injuries and objects must persist, relationships and clues must evolve consistently, and AI suggestions must not silently become canon.

Novel Writing treats fiction as an author-controlled project rather than a one-shot prose prompt. It supports:

- The full path from premise, story structure, and character arcs to reviewed chapters and a completed manuscript.
- A three-state model—`confirmed`, `inferred`, and `author-planned`—that keeps canon separate from interpretation and future plans.
- Layered character context: canonical dossiers, chapter character cards, and ephemeral scene profiles that preserve individuality without loading every character for every chapter.
- Phase-specific reading: story-level and hard continuity constraints before drafting, with fine voice, embodiment, and callback consistency checked during revision.
- Manual review, AI review with human curation, and AI review-and-revision with human curation.
- Timeline, relationship, mystery, and clue visualizations in author and spoiler-safe reader modes.
- Project-local storage for manuscript, worldbuilding, research, and structured story state.

## Why this workflow is reliable

```text
Premise and creative boundaries
    ↓
Master outline and character arcs
    ↓
Author selects the next chapter boundary
    ↓
Load relevant context, previous chapter, and continuity records
    ↓
Draft chapter → six-dimensional review → author-curated revision
    ↓
Preview candidate state → author confirmation → safe merge
    ↓
Timeline / relationship / clue visualization
    ↓
Continue chapter by chapter until the manuscript is complete
```

The order provides four important safeguards:

1. **Resolve intent before generating prose.** Questions stay anchored to material the author has already provided, reducing generic interrogation and unauthorized invention.
2. **Draft before changing canon.** New chapter information is presented as candidate state and becomes structured canon only after explicit author confirmation.
3. **Report contradictions before repairing them.** The AI cannot silently rewrite author decisions merely to make validation pass.
4. **Review before visualizing.** Dashboards are generated from reviewed, confirmed state rather than discarded prose or speculation.

## Core advantages

### The author controls canon

Every story-state item uses one of three certainty levels:

- `confirmed`: canon explicitly accepted by the author.
- `inferred`: a conclusion supported by the manuscript but not yet confirmed.
- `author-planned`: a future event, reveal, or secret the author intends to use.

This prevents suggestions, guesses, and unrevealed plans from silently entering canon.

### Layered character context

Recurring characters use canonical dossiers that explain how background, desire, contradiction, relationships, voice, and embodied habits cause behavior. Each selected chapter contains a compact character card with only the active cast's entry state, goal, pressure, knowledge boundary, activated traits, relationship posture, and exit change. Drafting derives temporary scene profiles from those two layers instead of loading every dossier or every chapter card.

Outlining checks story-level alignment and builds the chapter card. Drafting loads only active dossier sections and hard constraints that can invalidate a scene. The first revision pass broadens evidence for fine-grained voice, gesture, background echoes, motifs, descriptions, and callbacks. This keeps more context available for concrete prose while preserving character depth.

### Continuity is more than a timeline

Continuity auditing covers:

- Event order, elapsed time, travel, and recovery time.
- Location, injuries, fatigue, clothing, abilities, and environmental effects.
- Item ownership, transfer, consumption, damage, and access.
- What the author, reader, narrator, and each character separately know.
- Trust, obligation, conflict, intimacy, and relationship change.
- Foreshadowing, mysteries, promises, threats, and expected payoffs.

A hard knowledge-boundary rule applies: a character cannot answer from information they have never seen, heard, or otherwise learned.

### Complete six-dimensional chapter review

After completing a chapter, choose one of three modes:

1. `manual review only`
2. `auto review with human curation`
3. `auto review and auto-revise with human curation`

Automated review covers worldbuilding and continuity, pacing and development, clue subtlety, theme and focus, dialogue individuality, and narrative clarity. The author still decides which changes to accept.

### Author and spoiler-safe reader visualizations

Offline HTML dashboards support:

- Story chronology and causal relationships.
- Characters, factions, and changing relationships.
- Mysteries, clues, holders, red herrings, and payoff networks.
- Author mode with plans, hidden relationships, and unrevealed payoffs.
- Reader mode with author-only and spoiler information removed and internal identifiers re-anonymized.

### Safe, verifiable state updates

Chapter state follows a deterministic sequence: candidate extraction → complete preview → digest verification → author confirmation → atomic write → post-write validation. Failed updates cannot partially modify canonical state or silently overwrite an existing dashboard.

The repository includes 100 automated tests covering the data model, reference integrity, reader redaction, atomic publishing, path and symlink safety, CLI behavior, and the end-to-end workflow. These tests verify engineering behavior; they do not claim to measure literary quality.

## How it differs from common approaches

The following anonymized comparison summarizes differences observed across open-source fiction-writing tools without naming individual projects:

| Dimension | Novel Writing | Lightweight prompt tools | Large modular suites | RAG / graph systems |
| --- | --- | --- | --- | --- |
| Premise to manuscript | One complete workflow | Usually focused on generation or rewriting | Often complete, with a higher learning cost | Often complete, with a heavier workflow |
| Canon authority | Three-state model with author-confirmed merges | Usually relies on chat context | Depends on the module | Stateful, but author authority may be unclear |
| Continuity | Time, place, items, knowledge, relationships, and clues | Mostly prompt-based checks | Broad coverage with fragmented implementation | Strong retrieval with complex state governance |
| Data safety | Validation, digest binding, atomic publishing, and safe paths | Usually no deterministic write layer | Depends on the module | Often emphasizes retrieval over confirmed writes |
| Review | Six dimensions with human choice preserved | Usually one-pass polishing | Rich review modules | Often requires an additional pipeline |
| Visualization | Author and spoiler-safe reader views | Usually absent | May depend on a separate workbench | Often includes graphs without reader redaction |
| Maintainability | Standard-library runtime and 100 automated tests | Simple and quick to start | More files and dependencies | Strong engineering with heavier deployment |

The goal is not to write the fastest possible first draft. It is to help authors forget less, preserve authority, and avoid story-state pollution throughout a long project.

## Installation

Python 3.9 or later is required. Runtime scripts use only the Python standard library.

### Codex

```bash
git clone https://github.com/guantoubaozi/novel-writing.git
cp -R novel-writing ~/.codex/skills/novel-writing
```

Start a new session with:

```text
Use $novel-writing to create a new novel project.
```

You can also place the repository in the skill directory of any agent that supports the `SKILL.md` standard.

## Three-minute quick start

### 1. Initialize a project

```bash
python3 scripts/init_project.py ~/Documents/my-novel \
  --title "Letters from Mist Harbor" \
  --language en
```

### 2. Develop the story

```text
Use $novel-writing with the project at ~/Documents/my-novel.
Help me establish the central conflict, character motivations, creative boundaries, and master outline.
```

### 3. Draft the next chapter

```text
/novel:chapter
Project: ~/Documents/my-novel
Draft chapter one from the chapter plan. Load the relevant world, character, previous-chapter, and continuity context first.
```

### 4. Review and visualize

```text
/novel:review
Run auto review with human curation on the completed chapter.
```

```text
/novel:visualize
Preview the timeline, relationship, and clue changes from this chapter. After confirmation, generate the author dashboard.
```

## Supported operations

| Operation | Purpose |
| --- | --- |
| `/novel:new` | Initialize a project and establish its premise |
| `/novel:outline` | Create or revise the master outline and chapter plan |
| `/novel:chapter` | Draft the next author-selected chapter |
| `/novel:review` | Run the six-dimensional chapter review |
| `/novel:revise` | Revise from structure down to sentence level |
| `/novel:audit` | Validate structured continuity and report conflicts |
| `/novel:visualize` | Update and render story visualizations |
| `/novel:status` | Report chapter, word-count, mystery, clue, and relationship status |

## Free edition boundary

The free edition places no limits on novel length, chapter count, character count, reviews, or visualizations. It supports completing an entire novel.

To keep the edition focused and maintainable, this repository excludes the following advanced automation:

- Automatic decomposition of a full outline into volumes, chapters, and multi-scene generation batches.
- Automatic long-context compression, relevance assembly, and cache-freshness management.
- Automatic generation of tiered cross-session handoff prompts.

The free workflow keeps chapter boundaries author-maintained, loads context from relevant project files, and completes the manuscript one chapter at a time.

## Repository structure

```text
novel-writing/
├── SKILL.md
├── agents/openai.yaml
├── assets/
│   ├── project-template/
│   └── dashboard-template.html
├── references/
├── scripts/
├── tests/
└── examples/
```

## Tests

```bash
python3 -m pip install "pytest>=8,<10"
python3 -m pytest -q
```

Validate the Skill structure with:

```bash
python3 /path/to/skill-creator/scripts/quick_validate.py .
```

## License

[MIT License](LICENSE). Use it for personal writing, research, education, or commercial projects. Read [CONTRIBUTING.md](CONTRIBUTING.md) before contributing.
