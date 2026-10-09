# ADR-008 — Development-mode pinned installation registration

**Status:** Accepted
**Date:** 2026-10-09

## Context

Run creation pins a default launch-compatible Engine Installation and is gated on it (M3 issue #29). The API and data contract places installation registration outside the ordinary Project API as operator tooling. M3 has no operator tooling and no compatibility suite yet, so the pinned installation is never recorded and a user cannot start a Run through the browser. The M3 Definition of Done requires exactly that browser flow.

## Decision

When the coordinator starts in development mode with an available engine installation source, it registers the pinned installation if it is absent:

- identity (family, exact revision, adapter version) comes from adapter inspection of the configured source;
- the capability manifest comes from the adapter;
- the installation record is `SUPPORTED`, `default_for_new_runs`, and launch-compatible;
- registration is idempotent by identity and promotes the registered installation as the default for new runs.

Outside development mode, registration remains operator tooling backed by the compatibility process. The registration is not a compatibility-suite substitute; it exists only to make the documented development-mode execution path reachable end to end.

## Consequences

- The M3 browser flow works without manual database work: create Project, register at coordinator start, create Run, execute.
- Production registration and compatibility validation stay deliberate operations.
- The registered digest is an identity digest over revision, adapter version, and manifest, not a byte digest of the installation tree.
