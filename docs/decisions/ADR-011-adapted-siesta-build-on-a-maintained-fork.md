# ADR-011 — Adapted Siesta build on a maintained fork

**Status:** Accepted
**Date:** 2026-10-12

## Context

M4 (durable human interaction) needs engine-side capabilities the reviewed revision does not have: an external human-interaction channel, durable native pending-interaction state, and a waiting terminal outcome. ADR-010 chose an in-repo patch series applied at installation materialization time.

The project maintains `nashit-mashkoor/siesta`, a fork of the upstream repository. The fork's `main` is reset to the reviewed revision `20b149e0734b09730dfd22803d2695776fcf84b8`, so a fork-based adaptation starts from the exact reviewed code and stays attributable.

## Decision

The adapted Siesta build lives on the maintained fork as ordinary commits.

- `vendor/siesta` is repointed to the fork. The submodule pins the exact adapted commit.
- The M4 engine hooks are commits on the `kallula` adaptation branch, based on the reviewed revision `20b149e`. The fork's `main` tracks the reviewed revision and carries no adaptation.
- The Engine Installation identity continues to be the submodule revision (now the adapted commit) plus the adapter version and capability manifest. No installation materialization step is introduced.
- ADR-007's process-boundary launch mechanics remain: workspace injection, allowlisted child environment, native-state observation, and outcome classification. Only the engine source that is launched changes.
- ADR-010 is superseded: the in-repo patch series and its materialization are dropped.

## Consequences

- The adaptation is reviewable as commits with full history, and patch-application machinery is not needed.
- The exact reviewed base revision stays visible in the branch point and in this record.
- Submodule initialization now requires the fork, which is public.
- When the reviewed revision moves, the `kallula` branch is rebased and the submodule re-pinned; generic hooks should still be offered upstream.
- The fork is a documented adaptation, not a silent divergence: the README "Pinned engine" section names the fork, the branch, and the base revision.
