# ADR-009 — Development-mode engine model configuration override

**Status:** Accepted
**Date:** 2026-10-10

## Context

The Run Engine Runtime's `config/models.json` is materialized from the immutable Engine Installation until Run configuration snapshots carry resolved agent assignments. Full Agent Profile configuration arrives in M9. On a development machine whose Pi installation does not offer the installation's committed model provider, every real run fails at its first model call, and no supported override exists. Editing the vendored installation is not acceptable because it breaks exact revision attribution.

## Decision

The coordinator accepts an optional `ENGINE_MODELS_CONFIG` path. In development mode, when set, the coordinator writes that JSON file into each Run Engine Runtime as `config/models.json` before the engine launches. The file must define `planner`, `worker`, and `consultant`, each with `model` and `provider`. Invalid configuration fails the run with an adapter-class failure instead of launching a broken engine.

The override changes only the Run-scoped mutable runtime configuration. The immutable installation stays untouched, and provider authentication stays with the Pi profile that the engine child resolves through its own environment.

## Consequences

- Development runs can use the models the local Pi installation actually provides.
- The override is a deployment affordance, not a product configuration surface; M9 replaces it with Agent Profiles materialized from the Run configuration snapshot.
- The setting is documented in `.env.example`; non-development deployments do not apply it.
