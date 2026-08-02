# Post-Chapter Visualization Workflow

Use this workflow after a chapter is complete. Candidate extraction is non-canonical: no candidate becomes story truth, structured project data, a snapshot, or dashboard output until the author chooses an update path and explicitly confirms the proposed merge.

## Candidate extraction

Read the completed chapter and compare it with the canonical project data. Extract candidate changes in these groups:

- Timeline events, including their causal links.
- New characters and character-state changes.
- New, changed, ended, hidden, or one-sided relationships.
- Mysteries, clues, holders, interpretations, red herrings, confirmations, and payoffs.
- Contradictions between the completed chapter and canonical records.

Every candidate must contain a complete canonical record rather than a prose shorthand. Give the record a stable ID and include its canonical `visibility` and `source_refs`; `source_refs` must identify the completed chapter and the specific passage or span supporting the candidate. TimelineEvent, Relationship, Clue, and ClueLink records also carry their canonical `certainty` field. Character and Mystery records do not have canonical certainty: present each of those two candidate types in a presentation envelope such as `{"candidate_certainty":"inferred","record":{...}}`. Remove that envelope before packet construction; `candidate_certainty` does not enter the update packet or canonical JSON, and neither Character nor Mystery gains a persistent `certainty` field. Mark a conclusion not directly established by the chapter as `inferred`.

Present `confirmed`, `inferred`, and `author-planned` candidates in separate groups, using canonical `certainty` where the record defines it and the Character/Mystery `candidate_certainty` presentation envelope otherwise. A label describes evidence or author intent; it does not grant permission to merge. Report contradictions explicitly.

Never merge ambiguous changes.

Never merge any candidate without author confirmation.

## Author prompt

Translate the surrounding prompt into the project's language, but preserve the five English choice phrases exactly:

```text
This chapter is complete. I identified {event_count} timeline events,
{relationship_count} character or relationship changes, and {clue_count}
clue-network changes. Choose one:

1. update all and regenerate HTML
2. update structured data only
3. select visualizations
4. preview candidate changes
5. skip this chapter
```

The counts describe extracted candidates, not already accepted canonical changes. Do not interpret silence, an unrelated reply, or an ambiguous response as a choice or confirmation.

## Choices 1–3: confirmed update

For choices 1–3, bind author confirmation to one exact packet and follow these steps in order:

1. Create the packet in a private directory created with `mktemp -d`, set the directory mode to `0700`, and set the packet mode to `0600`. Prefer the system temporary area; if project-local temporary storage is required, keep the resolved directory under a dedicated non-canonical temporary root. Record the exact resolved directory and packet path. Never put the packet in a canonical data directory.
2. Compute the packet's SHA-256 digest from its final raw bytes and call it `DIGEST`. Do not rewrite the packet after computing this candidate digest.
3. Dry-run `python3 scripts/merge_story_updates.py PROJECT UPDATE --expected-sha256 DIGEST --dry-run` against that exact packet. The command verifies `DIGEST` inside the process before parsing those same bytes. If the digest differs or the dry-run reports a validation error or ambiguous record, do not merge, snapshot, or render; correct the packet, compute a new digest, and repeat from this step.
4. Present the complete grouped IDs, additions, replacements, and SHA-256 digest before asking for confirmation. Show every record under timeline, character relationships, or clue network and then under `confirmed`, `inferred`, or `author-planned`; include validation errors and ambiguous records explicitly, even when those lists are empty.
5. Confirm only when the author explicitly cites that exact SHA-256 digest. A choice number, “yes,” silence, or approval that does not cite the digest is not packet confirmation.
6. Recompute SHA-256 immediately before merge and require it to equal the confirmed digest. Compare the digest for the same resolved packet path that was dry-run and presented.
7. If the digest differs, do not merge; return to dry-run, presentation, and confirmation. Treat the changed bytes as a new packet even when its record IDs appear unchanged.
8. Merge only the exact confirmed packet with `python3 scripts/merge_story_updates.py PROJECT UPDATE --expected-sha256 DIGEST`. This process reads the update file once, compares SHA-256 in constant time, parses JSON from those same bytes, and exits nonzero without canonical writes on mismatch.
9. `merge_story_updates.py` validates before writing and publishes canonical files atomically. A rejected packet therefore has no canonical write; do not describe merge and later validation as a rollback-capable transaction.
10. Run `python3 scripts/validate_story_data.py PROJECT` immediately after the merge.
11. If post-merge validation unexpectedly fails, stop before HTML rendering and report possible external change or corruption; do not claim a rollback occurred. Preserve the failure evidence and require repair plus a new preview before any later render.
12. Apply the selected rendering branch only after the confirmed merge and successful validation.
13. In a `finally` step, delete only the exact temporary directory created for this packet. Verify that the cleanup target equals the recorded resolved `mktemp -d` directory; never broaden it to a parent, project root, glob, or reconstructed path.

## Choice 1: update all and regenerate HTML

After confirmed merge and successful validation, render all timeline, relationships, and clues views and regenerate HTML.

Run `python3 scripts/render_dashboard.py PROJECT --types timeline,relationships,clues --mode author`. This branch is not optional: if rendering or the required snapshot fails, report the failure and leave the previous dashboard in place rather than claiming choice 1 completed. A separately requested reader dashboard is additional output and does not replace the required author render.

## Choice 2: update structured data only

After confirmed merge and successful validation, never render HTML.

End after validation. Do not create a dashboard snapshot because no dashboard is being overwritten.

## Choice 3: select visualizations

After confirmed merge and successful validation, render only the author-selected timeline, relationships, or clues views in the selected author or reader mode.

Before building the packet, ask which of timeline, relationships, and clues to render and whether each requested output uses author or reader mode. Invoke `render_dashboard.py` only for that explicit selection; an empty or ambiguous selection returns to the author rather than defaulting to all views.

Run `python3 scripts/render_dashboard.py PROJECT --types SELECTED_TYPES --mode MODE`, where `SELECTED_TYPES` is the confirmed nonempty comma-separated subset and `MODE` is the confirmed `author` or `reader` mode.

Reader mode must omit hidden, author-planned, and otherwise author-only records. Generate a separate reader dashboard when requested; never derive it by exposing the author dashboard unchanged. Renderer implementation and reader filtering are outside this workflow contract; if the planned renderer is unavailable, report that limitation and do not fabricate HTML or an alternate command.

## Choice 4: preview candidate changes

This branch is preview-only and must not write packets, snapshots, canonical JSON, or HTML.

Present all candidate additions and replacements grouped under timeline, character relationships, and clue network. Within each group, show complete stable IDs and keep `confirmed`, `inferred`, and `author-planned` records distinct; call out contradictions and ambiguous records. Do not create an update packet or temporary directory, and do not invoke dry-run, merge, validation, snapshot, or render commands.

## Choice 5: skip this chapter

This branch makes zero changes and creates no packet, snapshot, JSON, or HTML.

Do not create a packet, snapshot, JSON change, or HTML change. Do not run dry-run, merge, validation, snapshot, or rendering commands. Return to writing support with the project exactly as it was before candidate extraction.

## Snapshot safety

Validate the chapter ID against `^[A-Za-z0-9_-]+$` before constructing any snapshot path. This permits ASCII letters, digits, hyphen, or underscore only. Reject path separators, dot paths such as `.` or `..`, and empty values. Do not normalize or repair an invalid ID into a path.

Resolve the source parent and destination parent and require each to remain contained in its configured dashboard or snapshot root.

Use path-component containment checks on resolved paths, never string-prefix checks.

Inspect every source and destination path component with non-following metadata before resolution.

Reject symlinks at the source, destination, or any checked parent.

If the chapter snapshot destination already exists, report a collision and do not overwrite it.

Create an owned per-destination lock with exclusive, no-follow creation and mode `0600`. Use the platform equivalent of `O_CREAT | O_EXCL | O_NOFOLLOW`; if lock creation reports `EEXIST`, stop without changing the existing snapshot or dashboard.

Create the owned temporary snapshot in the destination directory so source and publication remain on the same filesystem.

Flush, `os.fsync`, and close the complete temporary snapshot before publication.

Immediately before publication, repeat containment, component, symlink, and destination-absence checks while holding the owned lock.

Publish with atomic no-replace `os.link(temp, destination, follow_symlinks=False)` or an equivalent primitive that fails when the destination exists.

On `EEXIST`, preserve the existing snapshot and old dashboard, then stop.

Clean up only the owned temporary file and an owned lock; never remove or replace the destination.

If snapshot copy or publication fails, stop and do not overwrite the author dashboard.

After explicit author confirmation, a successful merge, and successful validation—but immediately before overwriting an author dashboard—create `visualizations/snapshots/<chapter-id>-author-dashboard.html` only if an existing author dashboard is present. Do not create a snapshot when no old dashboard exists. Do not snapshot during extraction, preview, dry-run, merge, or validation.

A reader dashboard has its own output lifecycle. Never use a reader render as the author-dashboard snapshot, and never include author-only records in reader output.
