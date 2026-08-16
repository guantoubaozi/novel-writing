# Contributing

Thank you for improving Novel Writing.

## Before you begin

- Search existing issues before starting work to avoid duplication.
- For feature changes, explain the author problem being solved and any effect on the existing project format.
- Do not submit real unpublished manuscripts, personal information, or copyrighted long-form text in tests, examples, or issues.

## Local validation

Python 3.9 or later is required.

```bash
python3 -m pip install "pytest>=8,<10"
python3 -m pytest -q
python3 /path/to/skill-creator/scripts/quick_validate.py .
```

## Design principles

- The author has final authority over canon.
- Inferences and author plans must never be silently promoted to `confirmed`.
- Report contradictions before proposing repairs.
- Preserve source drafts by default and never silently overwrite manuscript prose.
- Validate structured data before writing and ensure failures cannot leave partial updates.
- Reader views must not expose author-only, planned, or hidden information.
- Keep `SKILL.md` concise and place detailed rules in directly referenced files under `references/`.

## Pull Request

Pull requests should include:

1. The motivation and user scenario.
2. Behavioral changes and compatibility notes.
3. Added or updated tests.
4. Local test results.
