# ADR-007 — M3 Siesta adapter seam at the process boundary

**Status:** Accepted
**Date:** 2026-10-09

## Context

M3 must run the reviewed pinned Siesta revision through Kallula for the first time. The Siesta Adaptation Specification expects a Kallula-compatible engine build with an explicit programmatic entry point, workspace injection, structured event hooks, and structured terminal outcomes. The vendored revision is an unmodified Git submodule pinned to an exact upstream commit. The Implementation Plan allows development-process execution in M3 only.

The project must preserve exact revision attribution, avoid a silent fork of the engine, and still deliver trustworthy normalized state without parsing console text.

## Decision

The M3 adapter lives in `packages/engine/siesta` and adapts the unmodified pinned revision at the process boundary.

- Launch: the pinned revision runs as a controlled subprocess (`python -m pipeline <objective> --auto`) with the Run Engine Runtime as `SIESTA_FACTORY` and the installation source on `PYTHONPATH`.
- Workspace injection: because the pinned revision derives its project directory from the objective slug, the adapter binds that deterministic path to the canonical workspace with a symlink under `runtime/projects/`. The canonical workspace stays the only copy; no slug-uniqueness redirect can occur.
- Adapted skills: the upstream path convention `FACTORY.parent/.agents/skills` is satisfied with a read-only symlink to the installation's `.agents`.
- Child environment: an explicit allowlist; no wholesale `os.environ` inheritance. Explicitly approved values can be injected by the caller.
- Events and outcome: normalized events and the semantic terminal outcome are derived from structured native state (checkpoint file, project knowledge-base ledger, verification verdict) and process status. Console text is diagnostic only.
- Identity: engine revision is inspected from the pinned source through Git; adapter version and capability manifest are adapter-owned.

## Consequences

- The submodule stays unmodified and the exact upstream revision remains attributable.
- Event fidelity is limited to persisted native transitions until upstream or forked hooks exist; the adapter owns the pinned slug and native file-format knowledge and must be re-validated on engine updates.
- Terminal outcomes never treat a clean process exit as verified completion; the native verdict and ledger decide.
- When the adapted-build hooks land, event delivery can change behind the same engine interface without coordinator or UI changes.
