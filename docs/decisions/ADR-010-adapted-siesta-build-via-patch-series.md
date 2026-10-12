# ADR-010 — Adapted Siesta build via an in-repo patch series

**Status:** Accepted
**Date:** 2026-10-12

## Context

M4 (durable human interaction) needs engine-side capabilities the pinned upstream revision does not have: an external human-interaction hook, durable native pending-interaction state, and a `WAITING_FOR_HUMAN` terminal outcome. ADR-007 adapted the unmodified revision at the process boundary, which was sufficient for autonomous runs but cannot provide these hooks.

The Engine Installation identity must include or reference the exact adaptation revision (KSA-REQ-022), and the pinned upstream revision is static while the adaptation is developed. A GitHub fork would add a second repository to maintain and requires separate repository credentials; the vendored submodule stays the exact reviewed revision.

## Decision

The adapted Siesta build is a versioned patch series applied to the pristine pinned revision when the Engine Installation is materialized.

- The patch series lives in the repository (`packages/engine/siesta/patches/`) with an ordered manifest and content hashes.
- The coordinator materializes an installation copy from `vendor/siesta/factory` plus the patch series under the configured engine installation root, computes the installation digest from the revision, adapter version, patch-set hash, and capability manifest, and registers it. Materialization is idempotent and the installation is never mutated by Runs.
- The engine launches from the materialized installation, not directly from the vendored source. Standalone Siesta CLI behavior remains available from that build.
- ADR-007's process-boundary launch mechanics remain: workspace injection, allowlisted child environment, native-state observation, and outcome classification. Only the engine source that is launched changes.

## Consequences

- The exact upstream revision stays attributable and the adaptation is explicit, reviewable, and testable in this repository.
- No fork repository and no additional credentials are needed.
- The patch series must be maintained when the pinned revision moves (later milestones); upstreamable generic hooks should be proposed upstream rather than carried indefinitely.
- Installation materialization becomes part of engine registration and must be covered by tests.

Alternative considered: forking `jairorodriguezarias/siesta` and pinning the submodule to the fork. Rejected for M4 because the pinned revision is static and the fork adds repository and credential overhead; revisit if adaptation work becomes continuous.
