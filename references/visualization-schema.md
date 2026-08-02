# Story Visualization Schema

The canonical visualization records are UTF-8 JSON in `continuity/timeline.json`,
`continuity/relationships.json`, and `continuity/clues.json`. Each document is
an object with integer `schema_version: 1` and the collections below. Boolean
`true` is not an integer schema version. Every collection is an array of record
objects. Required fields never accept JSON `null`, and record fields not listed
below are rejected.

Every record has a stable string `id`. IDs use only lowercase ASCII letters,
digits, and hyphens, with these prefixes: chapters `ch-`, events `event-`,
characters `char-`, relationships `rel-`, mysteries `mystery-`, clues `clue-`,
and links `link-`. Each `source_refs` value is an array of strings; every item
is `chapter-id` or `chapter-id#anchor`. Arrays may be empty.

## Records and JSON types

- **TimelineEvent:** string `id`, `title`, `story_time`, `chapter`, `location`,
  `summary`, `kind`, `certainty`, `visibility`; integer `sequence` (never a
  boolean); arrays of strings `participants`, `causes`, `effects`,
  `source_refs`.
- **Character:** string `id`, `name`, `role`, `faction`, `status`,
  `first_chapter`, `notes`, `visibility`; arrays of strings `aliases`,
  `source_refs`. It has no canonical `certainty` field.
- **Relationship:** string `id`, `source`, `target`, `type`, `direction`,
  `status`, `start_chapter`, `end_chapter`, `description`, `certainty`,
  `visibility`; array of strings `source_refs`.
- **Mystery:** string `id`, `title`, `question`, `status`,
  `introduced_chapter`, `resolved_chapter`, `visibility`; array of strings
  `source_refs`. It has no canonical `certainty` field.
- **Clue:** string `id`, `title`, `description`, `status`,
  `introduced_chapter`, `planned_payoff`, `actual_payoff`, `certainty`,
  `visibility`; arrays of strings `known_by`, `source_refs`.
- **ClueLink:** string `id`, `source`, `target`, `type`, `certainty`,
  `visibility`; array of strings `source_refs`.

Content strings may be `""`. Every chapter field (`chapter`, `first_chapter`,
`start_chapter`, `end_chapter`, `introduced_chapter`, and `resolved_chapter`)
is either `""` when not yet assigned/applicable or a valid `ch-*` ID. IDs,
enum values, relationship/link endpoints, and individual `source_refs` items
cannot be empty.

`TimelineEvent.participants` and `Clue.known_by` reference Character IDs.
Every `TimelineEvent.causes` and `TimelineEvent.effects` item is a non-empty ID
referencing an existing canonical TimelineEvent, Character, Relationship,
Mystery, Clue, or ClueLink record. Cross-domain references are valid.
`Relationship.source` and `Relationship.target` reference Character IDs.
`ClueLink.source` and `ClueLink.target` may reference any Mystery, Clue,
Character, TimelineEvent, or Relationship ID.

## Candidate certainty

Character and Mystery certainty exists only in a non-canonical presentation envelope:
`{"candidate_certainty":"confirmed|inferred|author-planned","record":{...}}`.
The envelope supports grouped preview and confirmation, then does not enter an
update packet or canonical JSON. Do not add `candidate_certainty` or
`certainty` to a Character or Mystery record. TimelineEvent, Relationship,
Clue, and ClueLink candidates use their canonical `certainty` field.

## Allowed Values

- `certainty`: `confirmed` | `inferred` | `author-planned`
- `visibility`: `author` | `spoiler-safe`
- `TimelineEvent.kind`: `present` | `flashback` | `flashforward` | `parallel` | `reported`
- `Character.status`: `planned` | `active` | `absent` | `missing` | `dead` | `unknown`
- `Relationship.direction`: `directed` | `mutual`
- `Relationship.status`: `planned` | `active` | `strained` | `hidden` | `ended`
- `Mystery.status`: `open` | `partially-resolved` | `resolved`
- `Clue.status`: `planned` | `seeded` | `noticed` | `interpreted` | `confirmed` | `misleading` | `disproved` | `resolved`
- `ClueLink.type`: `supports` | `contradicts` | `misleads` | `reveals` | `possessed-by` | `points-to`
