# Project guidance

## Documentation

All Kallula project documentation is in `docs/`.

The documents in `docs/` represent the current state of the project. They are the source of truth for:

- product behavior
- architecture
- implementation decisions
- APIs
- security
- UX
- project status

Start with `README.md`. Then read the documents that are relevant to the task before you make changes.

Follow the documented design. Do not silently override or bypass decisions in `docs/`.

## Keep code and documentation synchronized

Code and documentation must never go out of sync.

For every code change:

- check whether the change affects documented behavior or decisions
- update all affected documents in the same change
- update cross-references when needed
- update project or implementation status when it changes

If code and documentation disagree, treat the mismatch as a defect.

A change is not complete while its documentation is stale.

Do not hide product or architecture decisions only in code.

## Design gaps

If implementation exposes a real design gap or conflict:

1. Identify the document that owns the decision.
2. Make the smallest necessary decision.
3. Update the relevant documentation.
4. Then implement the change.

## Implementation approach

- Work only on the scope required by the current documented plan.
- Prefer the smallest complete solution that satisfies the documented requirements.
- Do not add infrastructure, abstractions, or features for hypothetical future needs.
- Preserve established boundaries and invariants unless the documentation is intentionally changed.
- Add or update tests for changed behavior.

## Documentation style

When editing files in `docs/`:

- follow the existing structure and terminology
- use the same clear technical tone as the rest of the documentation
- use the established approximately 60% ASD-STE100 writing style
- prefer direct and precise language
- avoid unnecessary repetition
- use ASCII diagrams when a diagram improves understanding
- keep related documents and cross-references consistent

## Before finishing

Confirm that:

- the implementation matches the relevant documentation
- all affected documentation is updated
- project terminology remains consistent
- relevant tests pass
- no undocumented product or architecture decision was introduced
