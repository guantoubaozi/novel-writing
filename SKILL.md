---
name: novel-writing
description: Plan, draft, review, revise, audit, and visualize complete long-form fiction projects while preserving author authority and project-local canon. Use when an author provides a novel idea, character or worldbuilding notes, an outline, a chapter draft, revision requests, continuity questions, requests high-level style abstraction from a reference novel or their own text via /novel:style-import, or asks for /novel:new, /novel:outline, /novel:chapter, /novel:review, /novel:revise, /novel:audit, /novel:visualize, or /novel:status. Read supplied fiction before responding, ask content-anchored development questions by default, separate confirmed canon from inference and author plans, review completed chapters in six dimensions, and update structured story data or visualizations only after explicit author confirmation.
---

# Novel Writing

## For writers

This is not a one-click novel generator. It is an author-controlled writing partner that helps carry a story from a rough idea to a complete long-form manuscript through outlining, character development, chapter drafting, revision, continuity checks, and visual story tracking. The author keeps control of canon, voice, chapter boundaries, and every proposed change.

## Core workflow

Execute these stages in order:

1. Resolve the existing novel project or initialize one with `scripts/init_project.py`.
2. Load the project-local working set from [project-workflow.md](references/project-workflow.md). Read the previous chapter, relevant outline and character sections, voice guide, and continuity records; do not load the whole manuscript by default.
3. Read all newly supplied fiction content before evaluating, questioning, outlining, drafting, or revising it.
4. Apply [questioning.md](references/questioning.md) when development decisions remain. Ask 3–5 content-anchored questions unless the author skips questions or requests immediate output. Execute status, audit, review, and visualization requests directly.
5. Apply [research-workflow.md](references/research-workflow.md) only when factual research can materially change plausibility or a story decision.
6. Route the request to [plotting.md](references/plotting.md), [character-arcs.md](references/character-arcs.md), [character-context.md](references/character-context.md), drafting guidance below, [dialogue-and-clarity.md](references/dialogue-and-clarity.md), [continuity.md](references/continuity.md), or [revision.md](references/revision.md).
7. Preserve `confirmed`, `inferred`, and `author-planned` as separate certainty states. Merge no proposed state without explicit author confirmation.
8. Draft or revise the author-selected chapter. Follow the author-maintained chapter plan; do not automatically partition the full novel into chapters or run an automatic multi-batch chapter pipeline.
9. Save a completed chapter before review. Never silently overwrite a manuscript file; preserve the source unless the author requests an in-place edit.
10. Apply [chapter-review.md](references/chapter-review.md) and offer all three review modes. Resolve accepted revisions before updating structured state.
11. Apply [visualization-workflow.md](references/visualization-workflow.md). Extract candidate timeline, character, relationship, mystery, and clue changes; preview and merge them only through explicit author confirmation.
12. Continue with the next author-selected chapter until the manuscript is complete, then perform a whole-project continuity and revision pass.

## Operation routes

| Operation | Execute | Load |
| --- | --- | --- |
| `/novel:new` | Initialize the project; establish premise, constraints, and initial story state. | [project-workflow.md](references/project-workflow.md), [questioning.md](references/questioning.md), [plotting.md](references/plotting.md), [character-arcs.md](references/character-arcs.md) |
| `/novel:outline` | Develop the dramatic question, causal structure, character change, author-chosen chapter plan, and chapter character card for the active cast. | [project-workflow.md](references/project-workflow.md), [questioning.md](references/questioning.md), [plotting.md](references/plotting.md), [character-arcs.md](references/character-arcs.md), [character-context.md](references/character-context.md), [continuity.md](references/continuity.md) |
| `/novel:chapter` | Load the selected chapter card and exact active dossier sections, draft from confirmed hard constraints, and save the selected chapter for review. | [project-workflow.md](references/project-workflow.md), [character-context.md](references/character-context.md), [dialogue-and-clarity.md](references/dialogue-and-clarity.md), [continuity.md](references/continuity.md) |
| `/novel:review` | Run the selected manual, auto-review, or auto-review-and-revise mode. | [chapter-review.md](references/chapter-review.md), [dialogue-and-clarity.md](references/dialogue-and-clarity.md), [continuity.md](references/continuity.md) |
| `/novel:revise` | Preserve the source and revise in ordered passes. | [questioning.md](references/questioning.md), [revision.md](references/revision.md), [dialogue-and-clarity.md](references/dialogue-and-clarity.md), [continuity.md](references/continuity.md) |
| `/novel:audit` | Run `scripts/validate_story_data.py`; report contradictions before repairs. | [continuity.md](references/continuity.md), then [revision.md](references/revision.md) only for approved repairs |
| `/novel:visualize` | Preview candidate state changes, confirm a packet, and render selected views. | [visualization-schema.md](references/visualization-schema.md), [visualization-workflow.md](references/visualization-workflow.md) |
| `/novel:status` | Run `scripts/project_status.py`; summarize manuscript and continuity progress. | [project-workflow.md](references/project-workflow.md), [continuity.md](references/continuity.md) |
| `/novel:style-import` | Search for and confirm a permitted reference work; accept website, author-owned file, public-domain text, or pasted text; cache local samples; run the style-import scripts; review qualitative abstractions; and optionally add the approved abstract template to the project voice guide. Refuse living-author imitation and protected-text copying. | [style-import.md](references/style-import.md), [style-template-model.md](references/style-template-model.md), [dialogue-and-clarity.md](references/dialogue-and-clarity.md), [character-context.md](references/character-context.md) |

## CLI usage

- Initialize: `python3 scripts/init_project.py PROJECT_DIR --title TITLE [--language LANGUAGE]`.
- Show status: `python3 scripts/project_status.py PROJECT_DIR [--format text|json]`.
- Validate structured state: `python3 scripts/validate_story_data.py PROJECT_DIR`.
- Preview or merge an exact update packet: `python3 scripts/merge_story_updates.py PROJECT_DIR UPDATE_FILE [--expected-sha256 HEX] [--dry-run]`.
- Render an offline dashboard: `python3 scripts/render_dashboard.py PROJECT_DIR [--output FILE] [--mode author|reader] [--types timeline,relationships,clues]`.

Use `--expected-sha256` for every post-chapter merge. Present the exact digest with the complete candidate changes and merge only after the author confirms that digest.

## Drafting guidance

- Follow the confirmed chapter purpose, viewpoint, voice, chronology, knowledge boundaries, and style guide.
- Give each scene a concrete goal, active resistance, meaningful turn, and consequential outcome.
- Stage consequential conflict and relationship change as action and dialogue instead of summarizing the beat away.
- Show emotion through bodily signal, behavior, perception, and selective interiority rather than relying on bare feeling labels.
- Before drafting, read the selected chapter character card and exact active dossier sections according to [character-context.md](references/character-context.md); never read every dossier or chapter card by default.
- Keep pre-draft continuity to hard constraints that can invalidate the chapter. Defer detail consistency such as fine speech habits, gestures, minor descriptions, background echoes, motifs, and callbacks to the first revision pass unless one is itself a hard constraint.
- Derive ephemeral scene profiles for active speakers and maintain a knowledge ledger according to [dialogue-and-clarity.md](references/dialogue-and-clarity.md).
- If the project `style/voice.md` contains an approved style-import template, use it as the author's overall narrative and dialogue baseline. Treat quantitative signals as assistive checks only, never fixed sentence-length targets; preserve per-character voice, the name-blind test, and character-context rules, and follow the template's local copyright and permission boundaries.
- Preserve deliberate ambiguity while keeping actor, action, speaker, time, place, and referent clear.
- End where the chapter's change creates forward pressure; do not add a hook that contradicts its tone or resolution.

## Author authority and safety

- Never promote an inference, suggestion, or planned secret to confirmed canon without author confirmation.
- Report contradictions before proposing repairs and preserve the author's chosen canon.
- Treat brainstorming, summaries, review findings, and proposed prose as non-final until accepted.
- Never silently overwrite manuscript files or structured story data.
- Preserve the author's voice. Decline imitation of a living author's style and offer high-level craft traits instead.
- Keep manuscript, research, outline, state, and visualization outputs inside the author's project.
