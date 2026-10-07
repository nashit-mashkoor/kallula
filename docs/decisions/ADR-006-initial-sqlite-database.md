# ADR-006 — Initial SQLite development database and PostgreSQL switch

**Status:** Accepted
**Date:** 2026-10-07

## Context

The design documents target PostgreSQL 16+ for the hosted control-plane database. The first implementation milestones need a database that starts with zero setup on any developer machine and in CI, while the schema access must not be rewritten when deployment moves to PostgreSQL.

## Decision

Initial development uses SQLite through `aiosqlite`, configured by the single `DATABASE_URL` value and accessed only through SQLAlchemy 2.x and Alembic. PostgreSQL 16+ is restored for hosted or multi-process deployment by changing `DATABASE_URL` and running the migrations.

Schema definitions and queries stay dialect-neutral. PostgreSQL-only behavior — currently the `LISTEN/NOTIFY` wake-up signal — is enabled only when the database is PostgreSQL; SQLite uses a polling wake-up interval behind the same event-delivery contract.

## Consequences

- Zero-setup local development and CI.
- Switching databases is a configuration change plus a migration run, not a code change.
- Wake-up delivery keeps one contract with two backends.
- Features that require PostgreSQL-specific behavior must stay behind that boundary until the switch.
