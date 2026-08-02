# Chapter Review

## When to use

Offer this review after a chapter draft or revision completes, before merging any state. AI-drafted chapters commonly rush pacing, run thin, and expose foreshadowing too plainly, so surface the review by default rather than waiting for the author to request it.

Resolve the review before the post-chapter visualization workflow; do not extract visualization candidates until the review mode resolves.

## Review mode prompt

Translate the surrounding prompt into the project's language, but preserve the three English choice phrases exactly:

```text
This chapter is drafted. Choose how to review it:

1. manual review only
2. auto review with human curation
3. auto review and auto-revise with human curation
```

Do not interpret silence, an unrelated reply, or an ambiguous response as a choice. Default to mode 1 only when the author declines to choose.

## Review dimensions

Modes 2 and 3 run all six dimensions against supplied and project-recorded evidence. Cite the passage or record behind each finding, classify severity as in [continuity.md](continuity.md) where applicable, and never assert canon the chapter does not establish. Apply the operational tests in [dialogue-and-clarity.md](dialogue-and-clarity.md), not a generic preference for polished prose.

### Worldview, continuity, and knowledge boundaries

Check the chapter's characters, plot, and logic against the confirmed worldview, established rules, and prior clues. Flag any element that contradicts the story bible, the recorded continuity facts, open threads, or earlier chapters. For every consequential statement or response, verify how and when that character learned the concept; flag replies to terminology, motives, plans, history, or facts the character was never told or shown. Route contradictions through [continuity.md](continuity.md) and report them before proposing any fix.

### Pacing and expansion

Detect rushed story-advancement and description that runs too short or too fast for the scene's weight. Where pressure warrants it, propose an expansion pass that adds concrete detail, micro-expression, gesture and action, sensory grounding, and selective interiority to make the scene fuller and more vivid. Do not pad inert scenes or contradict the confirmed pacing plan; follow [revision.md](revision.md) pacing order.

Also flag the opposite fault: a consequential turn compressed into a summary sentence that should have been staged as a scene, and structural padding that slows the opening or dilutes the setting — a recap of the previous chapter aimed at readers who already read it, or a manual-style list of procedures, record fields, or specs that does not advance the scene. Propose staging the summarized turn and cutting the padding per [revision.md](revision.md).

### Foreshadowing subtlety

Find planted foreshadowing and hidden threads that the draft states too plainly, spelling out what should stay implied. Propose rewrites that make each such setup oblique — carried by concrete image, action, or offhand detail — so it functions as a genuine hidden thread with a later payoff rather than an announced one. Preserve fair-play evidence; keep the clue discoverable, only less overt.

### Theme and focus alignment

Revisit the novel's stated theme, core premise, and the focal characters' traits and individuality. Check whether the chapter expresses them, and flag content that drifts from the theme, dilutes the intended characterization, or overshadows the main line with a subordinate element. Propose refocusing that restores emphasis without flattening deliberate contrast.

### Dialogue individuality and naturalness

Check whether speakers have distinguishable cadence, vocabulary, precision, hesitation, completeness, humor, evasion, and subtext appropriate to identity, relationship, knowledge, emotion, and scene pressure. Run the name-blind, information-only, mechanical-exchange, pressure, and oral-language tests from [dialogue-and-clarity.md](dialogue-and-clarity.md). Flag stretches where multiple characters all speak in equally concise, accurate, mechanically efficient exchanges unless the context specifically requires clipped commands. Propose revisions that restore personal voice, conversational friction, physical context, and imperfect human expression without obscuring necessary plot information.

### Narrative clarity and explanatory restraint

Check whether an ordinary reader can identify the actor, action, location, referent, cause, and immediate consequence on one reading. Flag unfamiliar place names, technical terms, pronouns, and local positions whose meaning exists only in the author's mental map. Find explanatory sentences built from denial, compressed judgment, author-level summary, unsupported universals, or polished maxim-like phrasing. Prefer a concrete consequence, viewpoint observation, behavior, or failed action; retain a concise summary only when earlier evidence supports it and the viewpoint can make it.

Unless the author explicitly requests thematic elevation, also flag forced abstraction or uplift: a local action, practical outcome, or relationship beat restated as a profound general truth, predictive summary, chapter thesis, or thematic conclusion after the scene has already made the point. Recommend removing it or rewriting it as the plain action, position, dialogue, and consequence visible to the viewpoint character.

## Mode 1: manual review only

This mode runs no automatic review and leaves the chapter to human review. Make no findings, no expansion, and no revision. Return to the post-chapter visualization workflow with the chapter exactly as drafted.

## Mode 2: auto review with human curation

This mode runs the six-dimension automatic review to produce findings but does not revise the chapter. Present findings grouped by dimension with severity, cited evidence, and a proposed fix for each, so the author decides which findings to adopt and which to reject. Apply no manuscript change until the author selects specific findings; then route accepted fixes through [revision.md](revision.md).

## Mode 3: auto review and auto-revise with human curation

This mode runs the six-dimension review and then applies one automatic revision round as a proposed revision for human curation. Preserve the source per [revision.md](revision.md): produce the revised chapter as a proposal or diff, not an in-place overwrite, and summarize every change against its finding. Hand the revised chapter and the finding-to-change map to the author for human curation; the author still decides what to keep. Run exactly one auto-revision round, then stop and hand off.

## Report and author authority

Keep review findings and any auto-revision non-final until the author confirms. Report findings before proposing fixes, preserve confirmed canon and the author's voice and style guide, and never silently overwrite the manuscript. Merge structured story-state or proceed to visualization only after the review resolves and the author confirms any resulting change.
