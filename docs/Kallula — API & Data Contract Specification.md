# Kallula — API & Data Contract Specification

**Document status:** Normative API and data-contract specification — pre-implementation
**Product:** Kallula
**Primary product specification:** [`Kallula — Product Requirements Document.md`](./Kallula%20%E2%80%94%20Product%20Requirements%20Document.md)
**Parent architecture:** [`Kallula — System Architecture & State Model.md`](./Kallula%20%E2%80%94%20System%20Architecture%20%26%20State%20Model.md)
**Engine adaptation specification:** [`Kallula — Siesta Engine Adaptation Specification.md`](./Kallula%20%E2%80%94%20Siesta%20Engine%20Adaptation%20Specification.md)
**UX & interaction specification:** [`Kallula — UX & Interaction Specification.md`](./Kallula%20%E2%80%94%20UX%20%26%20Interaction%20Specification.md)
**Security & credentials design:** [`Kallula — Security & Credentials Design.md`](./Kallula%20%E2%80%94%20Security%20%26%20Credentials%20Design.md)
**Execution environment & Preview design:** [`Kallula — Execution Environment & Preview Design.md`](./Kallula%20%E2%80%94%20Execution%20Environment%20%26%20Preview%20Design.md)
**Implementation plan:** [`Kallula — Implementation Plan.md`](./Kallula%20%E2%80%94%20Implementation%20Plan.md)  
**Implementation status:** Not started
**Purpose:** Freeze Kallula's stable application-facing resources, logical persistence schema, field contracts, state and version identities, browser/API operations, durable command semantics, concurrency/idempotency rules, normalized events, replay/live-update behavior, security-sensitive omissions, and error contracts without leaking current Siesta-native implementation details into product-wide interfaces.
**Audience:** Frontend, backend/control-plane, runtime, engine integration, security, QA, data/migration, and future client developers.

> **Normative relationship:** Higher-level specifications define product behavior, state ownership, engine semantics, UX, security, and runtime isolation. This document **encodes those decisions**. It may choose stable data shapes and HTTP contracts, but it must not reopen the architecture. When a proposed API shape would contradict the Run state machine, Verified State rules, credential boundary, engine adapter boundary, or runtime model, the API shape must change.

> **Contract stability rule:** Public/browser-facing Kallula contracts use Kallula concepts. Current Siesta phase numbers, `stop.md`, `.pipeline-checkpoint`, native filenames, Pi process arguments, physical workspace paths, container IDs, and host implementation details are not stable product API fields.

---

# 1. Purpose

This specification defines the contract between:

- the Kallula browser client and Control Plane;
- Control Plane modules that persist product state;
- the Run Coordinator/Reconciler and durable control records;
- normalized engine/runtime event producers and the Event Journal;
- frontend live-update/replay consumers;
- trusted integration/runtime controllers and the Kallula records that represent their outcomes.

It answers:

- What is the canonical representation of a Project, Run, Execution Attempt, Pending Interaction, Work Item, Event, Artifact, Verified State, Preview, Credential, Profile, Engine Installation, Environment Snapshot, Runtime Plan, Integration, and Audit Event?
- Which resources are mutable versus immutable?
- How are mutations protected from stale clients?
- How are long-running actions represented?
- Which actions are commands rather than CRUD updates?
- What does command success mean?
- How are retries made idempotent?
- How does the frontend replay execution history after reconnect?
- How are live updates delivered?
- How are list endpoints paginated?
- How are errors classified?
- Which security-sensitive fields can never be returned?
- What relational/logical constraints preserve the architecture's invariants?
- Which data belongs in the control-state store versus workspace/object/log storage?

---

# 2. Scope and Non-Goals

This document freezes:

- versioned browser-facing HTTP API conventions;
- JSON field naming/types;
- stable resource schemas;
- list/pagination behavior;
- optimistic concurrency;
- idempotency;
- durable command contract;
- event schema;
- SSE replay/live-update contract;
- logical database entities/columns/constraints;
- security-sensitive write-only/never-returned fields;
- standard errors;
- cross-resource relationships;
- derived versus authoritative fields.

It intentionally does **not** choose:

- a specific Python web framework;
- PostgreSQL versus another relational database product;
- ORM;
- queue library;
- object-storage product;
- container-runtime library;
- SSE implementation library;
- frontend data-fetch library;
- exact database indexes beyond correctness-critical constraints;
- physical sharding/partitioning;
- cache technology;
- database migration framework.

The first implementation may choose those technologies as long as these contracts remain true.

---

# 3. API Style Decision

```text
Browser
   |
   | REST request
   v
+------------------+
| /api/v1          |
+---------+--------+
          |
          | stores durable intent
          v
+------------------+
| Command / State  |
+---------+--------+
          |
          | committed changes
          v
+------------------+
| Event Journal    |
+---------+--------+
          |
          | replay + live delivery
          v
        SSE
          |
          v
       Browser
```


Kallula v1 uses:

```text
Versioned JSON REST
+
Server-Sent Events (SSE) for durable event replay/live delivery
```

## 3.1 Why REST

Kallula's browser workflow is primarily:

- read durable state;
- create durable resources;
- submit typed commands;
- answer durable interactions;
- inspect evidence/history.

This maps cleanly to resource-oriented HTTP.

## 3.2 Why SSE

Execution updates are predominantly server-to-browser.

Kallula already has:

- durable normalized events;
- ordered per-Run event sequence;
- reconnect/replay requirements.

SSE provides:

- one-way live delivery;
- automatic reconnect support;
- standard HTTP authorization;
- event IDs for replay.

A WebSocket protocol is not required in v1.

## 3.3 SSE is not authoritative

If the live connection is lost:

- durable resources remain authoritative;
- events remain replayable;
- frontend refetches authoritative state.

SSE delivery failure never changes Run truth.

---

# 4. Base URL and Versioning

Browser-facing API base:

```text
/api/v1
```

Examples:

```text
GET  /api/v1/projects
GET  /api/v1/runs/{run_id}
POST /api/v1/runs/{run_id}/commands/stop
```

Breaking contract changes require a new API version or an explicitly compatible migration.

Adding:

- optional fields;
- new enum values where clients must tolerate unknown values;
- new endpoints;

does not necessarily require `/v2`.

---

# 5. JSON Conventions

## 5.1 Field naming

JSON field names use:

```text
snake_case
```

## 5.2 IDs

All Kallula resource IDs are JSON strings.

Example:

```json
{
  "id": "01K7..."
}
```

Clients must treat IDs as opaque.

The implementation may use UUIDv7/ULID/another collision-resistant sortable identifier internally, but:

- the string format is not semantic;
- clients do not parse timestamps/type information from IDs;
- IDs never change.

## 5.3 Timestamps

All API timestamps use RFC 3339/ISO 8601 UTC strings:

```text
2026-10-05T01:23:45.123Z
```

Database storage may use native timezone-aware timestamps.

## 5.4 Durations

Durations use integer milliseconds unless a field explicitly says otherwise.

## 5.5 Hashes

Content/configuration hashes are lowercase algorithm-prefixed strings where exposed:

```text
sha256:abcdef...
```

## 5.6 Enums

API enums use:

```text
UPPER_SNAKE_CASE
```

Clients must tolerate unknown future enum values by:

- rendering a safe fallback;
- not assuming exhaustive switch coverage for display-only values.

Clients must not silently submit unknown values back when a field is constrained.

## 5.7 Nullability

Fields are non-null unless the schema explicitly states `nullable`.

Absent optional field and explicit `null` are not automatically equivalent.

## 5.8 Arbitrary JSON

Open-ended JSON is allowed only where the contract explicitly marks a field:

```text
json_object
```

Stable product data should use typed fields rather than becoming one large JSON blob.

---

# 6. Common Resource Fields

Mutable top-level resources generally include:

| Field | Type | Meaning |
|---|---|---|
| `id` | ID | Stable resource identity |
| `created_at` | timestamp | Creation time |
| `updated_at` | timestamp | Last authoritative mutation |
| `version` | int64 | Monotonic resource version for optimistic concurrency |

Immutable records may omit `updated_at` or keep it equal to creation time.

## 6.1 Resource version

`version` begins at `1`.

Every meaningful mutation increments it atomically.

HTTP responses for versioned resources include:

```text
ETag: "v12"
```

---

# 7. Optimistic Concurrency

## 7.1 Mutable resource update

`PATCH`/`PUT`/security-sensitive `DELETE` operations require:

```text
If-Match: "v12"
```

when the caller is changing the current representation.

If omitted where required:

```text
428 Precondition Required
```

If stale:

```text
412 Precondition Failed
```

with the standard error contract and current resource version where safe.

## 7.2 Commands

Commands perform state validation atomically when accepted.

They do not need `If-Match` by default because:

- current Run state may change rapidly;
- the command has its own idempotency key;
- the command handler evaluates whether the action remains valid.

A command request may include optional expected-state fields for extra user-intent precision.

## 7.3 Interaction answers

Answering a Pending Interaction requires:

- interaction is still `OPEN`;
- Run/interaction ownership matches;
- one accepted response does not already exist.

The same response may be retried idempotently.

---

# 8. Idempotency

Side-effecting `POST` requests use:

```text
Idempotency-Key: <opaque client-generated string>
```

This is required for:

- resource creation where duplicate creation would be harmful;
- Run creation;
- durable commands;
- interaction answers;
- Credential create/replace;
- Preview creation;
- export/publish creation.

## 8.1 Idempotency scope

Key scope:

```text
authenticated principal
+ HTTP method
+ canonical endpoint
+ idempotency key
```

## 8.2 Same key, same request

Server returns the original durable result.

It must not perform the action twice.

## 8.3 Same key, different request

Return:

```text
409 Conflict
code = IDEMPOTENCY_KEY_REUSED
```

## 8.4 Retention

Idempotency records are retained for at least 24 hours.

Operations whose safe retry horizon must be longer may retain them longer.

The precise cleanup interval is operational policy.

---

# 9. Request Correlation

Every response includes or echoes:

```text
X-Request-Id
```

If the client supplies a syntactically valid `X-Request-Id`, Kallula may preserve it; otherwise the server generates one.

Request IDs:

- are diagnostic;
- are not authorization;
- are not resource IDs;
- never contain secrets.

Durable commands additionally have their own `command.id`.

---

# 10. Authentication Contract

The browser uses the server-managed session defined in the Security & Credentials Design.

## 10.1 Session resource

```text
GET /api/v1/session
```

Response when authenticated:

```json
{
  "authenticated": true,
  "principal": {
    "id": "principal-id",
    "display_name": "Nashit",
    "email": "user@example.com"
  },
  "session_expires_at": "2026-10-05T12:00:00Z"
}
```

Security policy may omit email depending on provider/privacy configuration.

## 10.2 Logout

```text
POST /api/v1/session/logout
```

Invalidates server session.

Authentication-provider login/callback routes may exist outside `/api/v1` because they are browser redirects rather than JSON product resources.

---

# 11. Authorization Contract

Every protected resource lookup is scoped by the authenticated principal.

A request for an inaccessible resource returns the product's configured non-disclosure behavior, normally:

```text
404 Not Found
```

rather than confirming another principal owns the ID.

Operator/admin-only diagnostics are separate authorization scopes and are not implied by normal Project ownership.

---

# 12. Standard List Response

Paginated list endpoints return:

```json
{
  "items": [],
  "next_cursor": null
}
```

## 12.1 Cursor

`next_cursor` is opaque.

Clients must not parse it.

## 12.2 Limit

Query:

```text
limit
```

Defaults to `50`.

Maximum v1 limit:

```text
100
```

## 12.3 Stable ordering

Every list endpoint defines its ordering.

Cursors encode enough ordering state to avoid simple offset-pagination drift.

---

# 13. Standard Error Contract

Errors use content type:

```text
application/problem+json
```

Body:

```json
{
  "type": "https://kallula.dev/problems/run-state-conflict",
  "title": "Run state does not allow this action",
  "status": 409,
  "code": "RUN_STATE_CONFLICT",
  "detail": "Run is already STOPPED.",
  "request_id": "req-id",
  "resource": {
    "type": "run",
    "id": "run-id"
  },
  "meta": {}
}
```

## 13.1 Required fields

- `type`
- `title`
- `status`
- `code`
- `request_id`

`detail`, `resource`, and `meta` are optional.

## 13.2 Security

`detail` and `meta` never contain:

- secret values;
- raw auth tokens;
- root paths that reveal host layout unnecessarily;
- provider Authorization headers.

---

# 14. Standard Error Codes

Core codes include:

```text
VALIDATION_ERROR
AUTHENTICATION_REQUIRED
AUTHORIZATION_DENIED
NOT_FOUND
PRECONDITION_REQUIRED
RESOURCE_VERSION_MISMATCH
IDEMPOTENCY_KEY_REUSED
STATE_CONFLICT
RUN_STATE_CONFLICT
PROJECT_EXECUTION_BUSY
INTERACTION_ALREADY_RESOLVED
INTERACTION_NOT_OPEN
RESUME_INCOMPATIBLE
ENGINE_INCOMPATIBLE
ENVIRONMENT_INCOMPATIBLE
CAPABILITY_UNSUPPORTED
CREDENTIAL_UNAVAILABLE
CREDENTIAL_REVOKED
INTEGRATION_AUTH_FAILED
RUNTIME_POLICY_DENIED
PREVIEW_NOT_RUNNABLE
RATE_LIMITED
DEPENDENCY_UNAVAILABLE
INTERNAL_ERROR
```

Domain-specific failure resources may contain richer classifications; HTTP errors should remain understandable and stable.

---

# 15. Durable Command Model

A **Command** represents accepted user/control intent.

It is not the same thing as the eventual target-resource outcome.

Examples:

- request safe stop;
- resume Run;
- answer interaction;
- stop Preview;
- publish source.

## 15.1 Command schema

```json
{
  "id": "command-id",
  "command_type": "SAFE_STOP_RUN",
  "target_type": "RUN",
  "target_id": "run-id",
  "state": "ACCEPTED",
  "actor_principal_id": "principal-id",
  "created_at": "2026-10-05T01:00:00Z",
  "applied_at": null,
  "failed_at": null,
  "failure": null,
  "result_refs": {}
}
```

## 15.2 Command states

```text
ACCEPTED
PROCESSING
APPLIED
FAILED
```

### `ACCEPTED`

Durably recorded and authorized.

### `PROCESSING`

A trusted controller is applying the intent.

### `APPLIED`

The command's **control effect** has been successfully applied.

Examples:

- safe-stop request is durably active;
- resume moved Run to `QUEUED`;
- interaction answer was accepted;
- Preview stop request was applied.

`APPLIED` does **not** mean:

- Run has completed;
- Run is already stopped;
- Preview is already gone;
- GitHub publish succeeded unless publish itself is the command's direct external operation and result is recorded accordingly.

### `FAILED`

The command could not be applied.

## 15.3 Command retrieval

```text
GET /api/v1/commands/{command_id}
```

Commands are immutable except for server-managed state/outcome fields.

---

# 16. Principal

Logical persistence:

```text
principals
```

Fields:

| Field | Type | Constraint |
|---|---|---|
| `id` | ID | PK |
| `auth_provider` | string | required |
| `auth_subject` | string | unique with provider |
| `display_name` | string | required |
| `email` | string? | nullable |
| `created_at` | timestamp | required |
| `updated_at` | timestamp | required |
| `version` | int64 | required |

`auth_subject` is server-side identity data and need not be returned in normal API responses.

---

# 17. Project Resource

## 17.1 Project schema

```json
{
  "id": "project-id",
  "display_name": "Expense Tracker",
  "owner_id": "principal-id",
  "origin": {
    "type": "NEW_IDEA",
    "repository": null
  },
  "workspace_status": "READY",
  "workspace_error": null,
  "default_engine_policy": {
    "mode": "PLATFORM_DEFAULT"
  },
  "default_agent_profile_version_id": "profile-version-id",
  "default_environment_profile_version_id": "env-profile-version-id",
  "engineering_preferences": {},
  "current_verified_state_id": "verified-state-id",
  "current_run_id": "run-id",
  "created_at": "2026-10-05T00:00:00Z",
  "updated_at": "2026-10-05T01:00:00Z",
  "version": 4
}
```

## 17.2 Origin

`origin.type`:

```text
NEW_IDEA
GITHUB_REPOSITORY
OTHER_REPOSITORY
```

For GitHub:

```json
{
  "type": "GITHUB_REPOSITORY",
  "repository": {
    "integration_id": "integration-id",
    "repository_id": "provider-repo-id",
    "full_name": "owner/repo",
    "selected_ref": "main"
  }
}
```

## 17.3 Workspace status

```text
INITIALIZING
READY
ERROR
```

This is setup/storage status, not Project lifecycle.

## 17.4 Derived fields

`current_run_id` and `current_verified_state_id` are pointers/projections.

They do not replace Run/Verified State history.

## 17.5 Project persistence

Logical table:

```text
projects
```

Correctness-critical columns:

```text
id
owner_id
display_name
origin_type
origin_metadata_json
workspace_id
workspace_status
workspace_error_code
default_engine_policy_json
default_agent_profile_version_id
default_environment_profile_version_id
engineering_preferences_json
current_verified_state_id nullable
current_run_id nullable
created_at
updated_at
version
```

Physical workspace path is not stored as a browser-visible field.

---

# 18. Project API

```text
GET  /api/v1/projects
POST /api/v1/projects
GET  /api/v1/projects/{project_id}
PATCH /api/v1/projects/{project_id}
```

## 18.1 Project list

Default ordering:

1. strongest derived attention;
2. most recently updated.

Supported filters:

```text
attention
run_state
workspace_status
query
cursor
limit
```

## 18.2 Create Project

Request:

```json
{
  "display_name": "Expense Tracker",
  "origin": {
    "type": "NEW_IDEA",
    "idea": "Build an expense tracker..."
  },
  "defaults": {
    "agent_profile_version_id": null,
    "environment_profile_version_id": null
  },
  "initial_run": {
    "clarification_mode": "INTERVIEW",
    "objective": "Build an expense tracker..."
  }
}
```

`initial_run` is optional.

If supplied:

- Project creation is durable first;
- initial Run creation occurs in the same product operation/transaction boundary where feasible;
- failure to start execution later does not erase the Project;
- response may include `initial_run_id`.

Response:

```text
201 Created
```

## 18.3 Patch Project

Mutable Project defaults only.

Examples:

- display name;
- default profile version;
- default environment profile version;
- engineering preferences.

Historical Runs do not change.

---

# 19. Workspace Resource

Workspace is mostly server-internal but has stable identity.

Logical table:

```text
workspaces
```

Fields:

```text
id
project_id unique
storage_driver
storage_key
created_at
validated_at nullable
status
metadata_json
```

Browser API never returns:

- host filesystem path;
- storage credential;
- mount path.

A Project response may expose only:

```json
{
  "workspace": {
    "status": "READY"
  }
}
```

---

# 20. Run Resource

## 20.1 Run schema

```json
{
  "id": "run-id",
  "project_id": "project-id",
  "ordinal": 15,
  "objective": "Implement CSV import",
  "control_state": "RUNNING",
  "stage": {
    "category": "EXECUTION",
    "native_id": null,
    "display_label": "Execution",
    "order": 4
  },
  "active_work_item_id": "work-item-id",
  "work_item_summary": {
    "completed": 3,
    "total": 7,
    "blocked": 0
  },
  "effective_config_snapshot_id": "run-config-id",
  "engine_installation_id": "engine-installation-id",
  "environment_snapshot_id": "environment-snapshot-id",
  "active_attempt_id": "attempt-id",
  "pending_interaction_id": null,
  "last_event_sequence": 184,
  "last_verified_state_id": "verified-state-id",
  "recovery": {
    "resume_allowed": false,
    "reason": null
  },
  "failure": null,
  "created_at": "2026-10-05T00:10:00Z",
  "started_at": "2026-10-05T00:10:03Z",
  "completed_at": null,
  "updated_at": "2026-10-05T01:22:00Z",
  "version": 28
}
```

## 20.2 Run states

Exactly:

```text
QUEUED
STARTING
RUNNING
WAITING_FOR_HUMAN
STOP_REQUESTED
STOPPED
FAILED
COMPLETED
```

## 20.3 Failure field

Nullable normalized object:

```json
{
  "class": "WORKER_LOST",
  "code": "WORKER_LOST",
  "summary": "Execution worker was lost before a terminal engine outcome.",
  "recoverability": "RESUMABLE",
  "evidence_artifact_ids": ["artifact-id"]
}
```

`recoverability`:

```text
RESUMABLE
RETRYABLE_AS_NEW_RUN
NOT_AUTOMATICALLY_RECOVERABLE
UNKNOWN
```

## 20.4 Run persistence

Logical table:

```text
runs
```

Columns:

```text
id
project_id
ordinal
objective
control_state
current_stage_category
current_stage_native_id nullable
current_stage_label nullable
current_stage_order nullable
active_work_item_id nullable
effective_config_snapshot_id
engine_installation_id
environment_snapshot_id
active_attempt_id nullable
pending_interaction_id nullable
last_event_sequence
last_verified_state_id nullable
failure_class nullable
failure_code nullable
failure_summary nullable
recoverability nullable
created_at
started_at nullable
completed_at nullable
updated_at
version
```

Constraints:

```text
unique(project_id, ordinal)
```

`COMPLETED` Runs never transition back to non-terminal state.

---

# 21. Run Creation API

```text
GET  /api/v1/projects/{project_id}/runs
POST /api/v1/projects/{project_id}/runs
GET  /api/v1/runs/{run_id}
```

Create request:

```json
{
  "objective": "Build the initial product",
  "clarification_mode": "INTERVIEW",
  "agent_profile_version_id": null,
  "environment_profile_version_id": null,
  "engine_selection": {
    "mode": "PROJECT_DEFAULT"
  }
}
```

`clarification_mode`:

```text
INTERVIEW
USE_SENSIBLE_DEFAULTS
```

Response:

```text
201 Created
```

Run is normally returned as:

```text
QUEUED
```

or `STARTING` if orchestration already claimed it.

Creation freezes the effective configuration snapshot before engine work begins.

---

# 22. Run Effective Configuration Snapshot

Immutable resource.

Logical table:

```text
run_config_snapshots
```

Fields:

```text
id
run_id unique
engine_installation_id
capability_manifest_hash
agent_profile_version_id
agent_slots_json
provider_model_assignments_json
reasoning_tool_settings_json
engineering_preferences_json
skill_identities_json
environment_profile_version_id
permitted_credential_refs_json
starting_git_commit nullable
starting_git_dirty boolean
starting_git_status_hash nullable
created_at
content_hash
```

No secret values.

API:

```text
GET /api/v1/runs/{run_id}/configuration
```

Response is read-only.

---

# 23. Execution Attempt Resource

## 23.1 Schema

```json
{
  "id": "attempt-id",
  "run_id": "run-id",
  "ordinal": 3,
  "state": "ACTIVE",
  "worker_runtime_ref": "opaque-runtime-ref",
  "engine_installation_id": "engine-installation-id",
  "environment_snapshot_id": "environment-snapshot-id",
  "started_at": "2026-10-05T01:20:00Z",
  "ended_at": null,
  "last_heartbeat_at": "2026-10-05T01:22:00Z",
  "terminal_reason": null,
  "observed_checkpoint": {
    "stage_category": "EXECUTION",
    "opaque_engine_state_ref": null
  },
  "log_stream_id": "log-stream-id"
}
```

Normal browser API may omit `worker_runtime_ref` unless advanced diagnostics are requested.

## 23.2 Attempt states

Persisted v1 enum:

```text
ALLOCATED
STARTING
ACTIVE
SUSPENDED
EXITED
LOST
```

## 23.3 Terminal reason

Examples:

```text
ENGINE_OUTCOME
WAITING_FOR_HUMAN
SAFE_STOP
PROCESS_EXIT_NONZERO
TIMEOUT
OOM
RUNTIME_LOST
SECURITY_TERMINATION
UNKNOWN
```

## 23.4 API

```text
GET /api/v1/runs/{run_id}/attempts
GET /api/v1/execution-attempts/{attempt_id}
```

Ordering: `ordinal ASC`.

---

# 24. Project Execution Lease

Lease is primarily internal and is not a normal browser-editable resource.

Logical table:

```text
project_execution_leases
```

Columns:

```text
project_id PK
run_id
attempt_id
holder_id
acquired_at
renewed_at
expires_at
lease_epoch
```

Correctness constraints:

- at most one row/active lease per Project;
- `lease_epoch` increases whenever ownership is reacquired;
- stale workers cannot renew using an old epoch.

Advanced diagnostics may expose:

```json
{
  "held": true,
  "run_id": "run-id",
  "attempt_id": "attempt-id",
  "last_renewed_at": "...",
  "expires_at": "..."
}
```

without exposing internal service credentials.

---

# 25. Run Command APIs

## 25.1 Safe stop

```text
POST /api/v1/runs/{run_id}/commands/stop
```

Request:

```json
{
  "mode": "SAFE"
}
```

Response:

```text
202 Accepted
```

with Command.

Valid primary states:

```text
RUNNING
WAITING_FOR_HUMAN
```

On acceptance, Run becomes or remains:

```text
STOP_REQUESTED
```

according to atomic state rules.

Command `APPLIED` does not imply Run `STOPPED`.

## 25.2 Resume

```text
POST /api/v1/runs/{run_id}/commands/resume
```

Request:

```json
{
  "reason": "USER_REQUEST"
}
```

Valid source states:

```text
STOPPED
FAILED
```

only when `recovery.resume_allowed == true` and compatibility passes.

On application:

```text
Run -> QUEUED
```

A later new Execution Attempt is created.

## 25.3 No force-resume

There is no v1:

```text
force=true
```

bypass for incompatibility.

---

# 26. Pending Interaction Resource

## 26.1 Schema

```json
{
  "id": "interaction-id",
  "run_id": "run-id",
  "attempt_id": "attempt-id",
  "kind": "QUESTION",
  "status": "OPEN",
  "title": "Requirements question",
  "prompt": "What should happen when a user's session expires?",
  "recommendation": "Redirect to sign-in and preserve the intended destination.",
  "context": {
    "accepted_turns": [
      {
        "question": "Who is the primary user?",
        "answer": "Individual freelancers."
      }
    ]
  },
  "allowed_responses": [
    "ANSWER",
    "USE_RECOMMENDATION",
    "DELEGATE_REMAINING"
  ],
  "created_at": "2026-10-05T00:15:00Z",
  "resolved_at": null,
  "version": 1
}
```

## 26.2 Kinds

```text
QUESTION
FINAL_INTENT_CONFIRMATION
```

Future kinds may be added.

## 26.3 Status

```text
OPEN
ANSWERED
DELEGATED
CANCELED
SUPERSEDED
```

## 26.4 Persistence

Logical table:

```text
pending_interactions
```

Columns:

```text
id
run_id
attempt_id nullable
kind
status
title
prompt
recommendation nullable
context_json
allowed_responses_json
engine_interaction_token
created_at
resolved_at nullable
version
```

`engine_interaction_token` is adapter-facing and may be omitted from browser responses.

v1 constraint:

```text
at most one OPEN interaction per Run
```

---

# 27. Interaction Response

Logical table:

```text
interaction_responses
```

Fields:

```text
id
interaction_id unique
run_id
actor_principal_id
response_type
answer_text nullable
created_at
command_id
```

`response_type`:

```text
ANSWER
USE_RECOMMENDATION
CONFIRM
REQUEST_CHANGE
DELEGATE_REMAINING
```

The accepted response is immutable.

---

# 28. Interaction API

```text
GET  /api/v1/interactions?status=OPEN
GET  /api/v1/interactions/{interaction_id}
POST /api/v1/interactions/{interaction_id}/commands/respond
```

Request examples.

Answer:

```json
{
  "response_type": "ANSWER",
  "answer": "Redirect the user to sign-in and preserve the original route."
}
```

Use recommendation:

```json
{
  "response_type": "USE_RECOMMENDATION"
}
```

Confirm final intent:

```json
{
  "response_type": "CONFIRM"
}
```

Request change:

```json
{
  "response_type": "REQUEST_CHANGE",
  "answer": "Also support recurring expenses."
}
```

Delegate:

```json
{
  "response_type": "DELEGATE_REMAINING"
}
```

Response:

```text
202 Accepted
```

with Command.

Duplicate retry with same idempotency key returns original Command.

A second materially different response after resolution returns:

```text
409
INTERACTION_ALREADY_RESOLVED
```

---

# 29. Stage Representation

Stage is embedded/projected rather than a standalone CRUD resource.

Schema:

```json
{
  "category": "EXECUTION",
  "display_label": "Execution",
  "order": 4,
  "native_id": null
}
```

Stable `category` values:

```text
REQUIREMENTS
SPECIFICATION
PLANNING
EXECUTION
REVIEW
VERIFICATION
LEARNING
COMPLETED
OTHER
```

For `OTHER`, `display_label` is required.

`native_id` is optional advanced diagnostic data and is not required for frontend logic.

---

# 30. Work Item Resource

## 30.1 Schema

```json
{
  "id": "work-item-id",
  "run_id": "run-id",
  "engine_key": "issue:4",
  "ordinal": 4,
  "title": "CSV Import",
  "description": "Import transactions from CSV.",
  "acceptance_criteria": [],
  "state": "ACTIVE",
  "blocker": null,
  "related_commit": null,
  "attempt_count": 1,
  "created_at": "...",
  "updated_at": "...",
  "version": 5
}
```

## 30.2 States

```text
PENDING
ACTIVE
COMPLETED
BLOCKED
SKIPPED
UNKNOWN
```

`engine_key` is adapter-owned stable correlation within the Run, not a globally stable Siesta concept.

## 30.3 Persistence

Logical table:

```text
work_items
```

Constraints:

```text
unique(run_id, engine_key)
unique(run_id, ordinal) where ordinal is not null
```

## 30.4 API

```text
GET /api/v1/runs/{run_id}/work-items
GET /api/v1/work-items/{work_item_id}
```

Work Items are engine projections and are not browser-editable in v1.

---

# 31. Event Resource

Events form the durable normalized execution journal.

## 31.1 Schema

```json
{
  "id": "event-id",
  "run_id": "run-id",
  "sequence": 184,
  "attempt_id": "attempt-id",
  "source": "ENGINE_ADAPTER",
  "source_event_sequence": 27,
  "event_type": "TEST_RUN_COMPLETED",
  "category": "TESTS",
  "severity": "INFO",
  "stage": {
    "category": "EXECUTION",
    "display_label": "Execution",
    "order": 4
  },
  "work_item_id": "work-item-id",
  "summary": "31 tests passed.",
  "payload_version": 1,
  "payload": {
    "passed": 31,
    "failed": 0,
    "skipped": 0
  },
  "artifact_ids": ["artifact-id"],
  "occurred_at": "2026-10-05T01:16:20Z",
  "recorded_at": "2026-10-05T01:16:20.120Z"
}
```

## 31.2 Ordering

`sequence` is monotonically increasing per Run.

Constraint:

```text
unique(run_id, sequence)
```

## 31.3 Source idempotency

For adapter-emitted current Siesta events:

```text
unique(attempt_id, source_event_sequence)
```

where those fields are present.

This implements the adaptation spec's source identity.

## 31.4 Sources

```text
CONTROL_PLANE
RUN_COORDINATOR
ENGINE_ADAPTER
RUNTIME_MANAGER
PREVIEW_CONTROLLER
INTEGRATION
SECURITY
```

## 31.5 Severity

```text
DEBUG
INFO
WARNING
ERROR
```

Normal Activity UX usually filters `DEBUG`.

---

# 32. Core Event Types

The exact list may grow, but v1 establishes stable names for important classes:

```text
RUN_QUEUED
RUN_STARTING
RUN_STARTED
RUN_WAITING_FOR_HUMAN
RUN_STOP_REQUESTED
RUN_STOPPED
RUN_FAILED
RUN_COMPLETED

ATTEMPT_ALLOCATED
ATTEMPT_STARTED
ATTEMPT_EXITED
ATTEMPT_LOST

STAGE_STARTED
STAGE_COMPLETED

WORK_ITEM_DISCOVERED
WORK_ITEM_STARTED
WORK_ITEM_COMPLETED
WORK_ITEM_BLOCKED
WORK_ITEM_SKIPPED

INTERACTION_OPENED
INTERACTION_RESOLVED

TEST_RUN_STARTED
TEST_RUN_COMPLETED
VERIFICATION_STARTED
VERIFICATION_COMPLETED
VERIFIED_STATE_CREATED

GIT_COMMIT_CREATED
ARTIFACT_DISCOVERED

PREVIEW_REQUESTED
PREVIEW_BUILD_STARTED
PREVIEW_AVAILABLE
PREVIEW_FAILED
PREVIEW_STOPPED

INTEGRATION_OPERATION_STARTED
INTEGRATION_OPERATION_COMPLETED

SECURITY_POLICY_DENIED
```

Unknown future event types remain displayable through `summary`.

---

# 33. Event Persistence

Logical table:

```text
events
```

Columns:

```text
id
run_id
sequence
attempt_id nullable
source
source_event_sequence nullable
event_type
category
severity
stage_category nullable
stage_native_id nullable
stage_label nullable
stage_order nullable
work_item_id nullable
summary
payload_version
payload_json
artifact_ids_json
occurred_at
recorded_at
```

Event rows are append-only.

Corrections happen through:

- new events;
- projection reconciliation;

not by rewriting historical event semantics casually.

---

# 34. Event Replay API

```text
GET /api/v1/runs/{run_id}/events
```

Query:

```text
after_sequence
before_sequence
category
severity
limit
```

Default ordering:

```text
sequence ASC
```

Example:

```text
GET /api/v1/runs/run-id/events?after_sequence=180&limit=100
```

Response:

```json
{
  "items": [
    { "sequence": 181 },
    { "sequence": 182 }
  ],
  "next_cursor": null
}
```

For Run events, `after_sequence` is preferred over opaque cursor because the sequence itself is a stable Run-local contract.

---

# 35. Run Event SSE

```text
GET /api/v1/runs/{run_id}/events/stream
```

Client may supply:

```text
Last-Event-ID: 184
```

or query:

```text
after_sequence=184
```

SSE frame:

```text
id: 185
event: run_event
data: { ...Event JSON... }
```

## 35.1 Connection behavior

On connect:

1. authorize Run;
2. replay events after requested sequence;
3. continue live delivery.

## 35.2 Keepalive

Server may emit SSE comments/keepalives.

They are not product events.

## 35.3 Gap handling

If requested sequence is no longer available because retention policy removed it:

```text
410 Gone
code = EVENT_CURSOR_EXPIRED
```

Response metadata includes:

- earliest available sequence;
- current Run `last_event_sequence`.

The frontend then refetches authoritative Run state and available history.

## 35.4 Duplicate delivery

Clients must tolerate duplicate SSE delivery.

`event.id`/`sequence` deduplicates.

---

# 36. Account/Project Live Invalidations

Dashboard and Project shell state do not need one SSE connection per Run.

Kallula provides an account-scoped lightweight stream:

```text
GET /api/v1/stream
```

This stream carries **invalidation/update notices**, not the authoritative Run event journal.

Frame:

```text
event: resource_changed
id: opaque-stream-cursor
data: {
  "resource_type": "RUN",
  "resource_id": "run-id",
  "project_id": "project-id",
  "version": 29,
  "reason": "STATE_CHANGED"
}
```

Other possible event:

```text
attention_changed
```

On reconnect or any gap, frontend refetches affected resources.

This stream may use an opaque cursor rather than Run sequence.

---

# 37. Artifact Resource

## 37.1 Schema

```json
{
  "id": "artifact-id",
  "project_id": "project-id",
  "run_id": "run-id",
  "attempt_id": "attempt-id",
  "artifact_class": "TEST_EVIDENCE",
  "display_name": "Regression test output",
  "media_type": "text/plain",
  "size_bytes": 8421,
  "content_hash": "sha256:...",
  "storage_kind": "WORKSPACE_REFERENCE",
  "source_identity": {
    "git_commit": "abc123"
  },
  "created_at": "...",
  "metadata": {}
}
```

## 37.2 Artifact classes

Stable initial values:

```text
INTENT
INTERVIEW_TRANSCRIPT
SPECIFICATION
PLAN
SOURCE_EXPORT
TEST_EVIDENCE
VERIFICATION_EVIDENCE
ENGINE_CHECKPOINT
CONSULTATION
REVIEW
KNOWLEDGE
LEARNING
RECOVERY
RUNTIME_LOG
ENGINE_LOG
OTHER
```

## 37.3 Storage kinds

```text
WORKSPACE_REFERENCE
RUN_ENGINE_RUNTIME_REFERENCE
LOG_REFERENCE
OBJECT_REFERENCE
GENERATED_EXPORT
```

Browser API never exposes a host filesystem path.

## 37.4 Persistence

Logical table:

```text
artifacts
```

contains metadata/reference only.

Raw content may live elsewhere.

---

# 38. Artifact API

```text
GET /api/v1/runs/{run_id}/artifacts
GET /api/v1/artifacts/{artifact_id}
GET /api/v1/artifacts/{artifact_id}/content
```

`content`:

- authorizes access;
- applies redaction policy where artifact class requires controlled rendering;
- may stream bytes;
- uses `Content-Type` and `Content-Disposition`.

Canonical source files should generally use the Files API rather than pretending each file is an Artifact.

---

# 39. Verification Result

## 39.1 Schema

```json
{
  "id": "verification-result-id",
  "run_id": "run-id",
  "source_identity": {
    "git_commit": "def456"
  },
  "outcome": "PASSED",
  "mechanical_test_summary": {
    "passed": 42,
    "failed": 0,
    "skipped": 1
  },
  "runtime_smoke": {
    "status": "PASSED"
  },
  "blocked_work_item_count": 0,
  "evidence_artifact_ids": ["artifact-id"],
  "started_at": "...",
  "completed_at": "..."
}
```

## 39.2 Outcomes

```text
PASSED
FAILED
INCONCLUSIVE
```

A model statement alone cannot produce `PASSED`.

## 39.3 Persistence

Logical table:

```text
verification_results
```

Rows are immutable evidence records.

---

# 40. Verified State

A Verified State points to the exact source that passed product verification.

## 40.1 Schema

```json
{
  "id": "verified-state-id",
  "project_id": "project-id",
  "run_id": "run-id",
  "verification_result_id": "verification-result-id",
  "git_commit": "def456",
  "created_at": "...",
  "summary": {
    "tests_passed": 42,
    "runtime_smoke": "PASSED"
  }
}
```

## 40.2 Rules

A Verified State is created only when:

- verification result is `PASSED`;
- no blocking condition prevents verified completion;
- exact source identity is known.

## 40.3 Project pointer

`projects.current_verified_state_id` may move forward to the newest accepted Verified State.

Historical states remain immutable.

## 40.4 API

```text
GET /api/v1/projects/{project_id}/verified-states
GET /api/v1/verified-states/{verified_state_id}
```

---

# 41. Files API

Files are read from canonical source or an immutable selected source identity.

## 41.1 Source selector

Query:

```text
source=current
```

or:

```text
source=verified:{verified_state_id}
```

or:

```text
source=commit:{git_sha}
```

Authorization and Git containment apply.

## 41.2 Directory listing

```text
GET /api/v1/projects/{project_id}/files
```

Query:

```text
source
path
```

Response:

```json
{
  "source": {
    "kind": "CURRENT",
    "git_commit": "abc123",
    "dirty": true
  },
  "path": "",
  "entries": [
    {
      "name": "README.md",
      "path": "README.md",
      "type": "FILE",
      "size_bytes": 1200
    },
    {
      "name": "src",
      "path": "src",
      "type": "DIRECTORY"
    }
  ]
}
```

## 41.3 Text content

```text
GET /api/v1/projects/{project_id}/files/content
```

For supported text-size bounds:

```json
{
  "path": "README.md",
  "source": {...},
  "encoding": "utf-8",
  "content": "# ..."
}
```

## 41.4 Raw download

```text
GET /api/v1/projects/{project_id}/files/raw
```

Streams file bytes.

## 41.5 Security

Paths:

- are workspace-relative;
- cannot contain traversal outside root;
- do not follow host-escaping symlinks through Kallula-managed access.

Files API is read-only in v1.

---

# 42. Git API

Read-only browser-facing Git inspection:

```text
GET /api/v1/projects/{project_id}/git/status
GET /api/v1/projects/{project_id}/git/commits
GET /api/v1/projects/{project_id}/git/commits/{sha}
GET /api/v1/projects/{project_id}/git/diff
```

## 42.1 Status

Response includes:

```json
{
  "branch": "kallula/run-15",
  "head": "abc123",
  "dirty": true,
  "changed_paths": 4,
  "ahead": null,
  "behind": null,
  "verified_commit": "def456"
}
```

## 42.2 Commit list

Cursor paginated.

## 42.3 Diff

Query:

```text
from
to
path
```

Large diffs may be truncated with explicit metadata.

No endpoint accepts arbitrary Git command strings.

---

# 43. Source Export

Export is a durable asynchronous resource.

```text
POST /api/v1/projects/{project_id}/exports
GET  /api/v1/exports/{export_id}
GET  /api/v1/exports/{export_id}/download
```

Create:

```json
{
  "source": {
    "kind": "CURRENT_COMMITTED"
  },
  "include_git_history": false,
  "format": "ZIP"
}
```

Export states:

```text
QUEUED
BUILDING
READY
FAILED
EXPIRED
```

Source export never includes:

- credential store;
- Run Engine Runtime;
- host paths;
- Preview runtime data;
- platform secrets.

---

# 44. Engine Installation Resource

## 44.1 Schema

```json
{
  "id": "engine-installation-id",
  "engine_family": "SIESTA",
  "engine_revision": "20b149e...",
  "adapter_version": "1.0.0",
  "installation_digest": "sha256:...",
  "status": "SUPPORTED",
  "default_for_new_runs": true,
  "compatibility": {
    "launch": "SUPPORTED",
    "state_format": "SUPPORTED",
    "resume": "SUPPORTED",
    "security": "SUPPORTED",
    "runtime": "SUPPORTED"
  },
  "capability_manifest": {...},
  "created_at": "..."
}
```

## 44.2 Status

```text
CANDIDATE
SUPPORTED
DEPRECATED
BLOCKED
```

## 44.3 Compatibility dimension

```text
SUPPORTED
UNSUPPORTED
UNKNOWN
```

## 44.4 API

```text
GET /api/v1/engine-installations
GET /api/v1/engine-installations/{engine_installation_id}
```

Normal user API is read-only.

Installation/promotion is operator tooling outside ordinary Project API in v1.

---

# 45. Capability Manifest

Capability Manifest is immutable/versioned content belonging to Engine Installation.

Schema shape:

```json
{
  "schema_version": 1,
  "interaction": {
    "human_requirements": true,
    "autonomous_defaults": true
  },
  "run_control": {
    "safe_stop": true,
    "resume": true
  },
  "work_items": true,
  "review": true,
  "verification": true,
  "learning": true,
  "runtime_smoke": true,
  "agent_slots": [
    {
      "key": "planner",
      "display_name": "Planner",
      "configurable_fields": [
        "provider",
        "model",
        "reasoning"
      ]
    }
  ],
  "artifacts": [
    "SPECIFICATION",
    "PLAN",
    "TEST_EVIDENCE"
  ]
}
```

The frontend may gate controls from this manifest plus Kallula product capabilities.

---

# 46. Agent Profile

Agent Profile has stable identity plus immutable versions.

Logical tables:

```text
agent_profiles
agent_profile_versions
```

## 46.1 Agent Profile

```json
{
  "id": "profile-id",
  "name": "Default",
  "owner_id": "principal-id",
  "current_version_id": "profile-version-id",
  "created_at": "...",
  "updated_at": "...",
  "version": 3
}
```

## 46.2 Agent Profile Version

```json
{
  "id": "profile-version-id",
  "agent_profile_id": "profile-id",
  "version_number": 4,
  "engine_family": "SIESTA",
  "slot_configurations": [
    {
      "slot_key": "planner",
      "provider": "ollama",
      "model": "glm-5.2:cloud",
      "reasoning": "DEFAULT",
      "editable_instructions": null,
      "skills": []
    }
  ],
  "content_hash": "sha256:...",
  "created_at": "..."
}
```

Versions are immutable.

---

# 47. Agent Profile API

```text
GET  /api/v1/agent-profiles
POST /api/v1/agent-profiles
GET  /api/v1/agent-profiles/{profile_id}
PATCH /api/v1/agent-profiles/{profile_id}
GET  /api/v1/agent-profiles/{profile_id}/versions
POST /api/v1/agent-profiles/{profile_id}/versions
GET  /api/v1/agent-profile-versions/{version_id}
```

`PATCH` changes metadata such as name/default marker.

Configuration changes create a new version.

Creating a new version validates against selected Engine Installation/capabilities before it can be used.

---

# 48. Environment Profile

Stable identity plus immutable versions.

Logical tables:

```text
environment_profiles
environment_profile_versions
```

## 48.1 Profile

```json
{
  "id": "environment-profile-id",
  "name": "Auto",
  "owner_id": "principal-id",
  "current_version_id": "environment-profile-version-id",
  "created_at": "...",
  "updated_at": "...",
  "version": 2
}
```

## 48.2 Version

```json
{
  "id": "environment-profile-version-id",
  "environment_profile_id": "environment-profile-id",
  "version_number": 2,
  "mode": "AUTO",
  "desired_capabilities": {
    "languages": [],
    "supporting_services": []
  },
  "resource_policy": {
    "class": "DEFAULT"
  },
  "network_policy": {
    "mode": "PUBLIC_INTERNET"
  },
  "content_hash": "sha256:...",
  "created_at": "..."
}
```

`mode`:

```text
AUTO
EXPLICIT
```

---

# 49. Environment Snapshot

Immutable Run-level resolved environment.

## 49.1 Schema

```json
{
  "id": "environment-snapshot-id",
  "run_id": "run-id",
  "profile_version_id": "environment-profile-version-id",
  "runtime_pack": {
    "key": "python-node",
    "image_digest": "sha256:...",
    "architecture": "amd64"
  },
  "language_runtimes": {
    "python": "3.12",
    "node": "22"
  },
  "resource_limits": {
    "cpu_millis": 2000,
    "memory_mb": 4096,
    "pids": 512,
    "attempt_timeout_ms": 7200000
  },
  "network_policy": {
    "mode": "PUBLIC_INTERNET"
  },
  "supporting_service_capabilities": [
    "POSTGRES",
    "REDIS"
  ],
  "content_hash": "sha256:...",
  "created_at": "..."
}
```

API:

```text
GET /api/v1/runs/{run_id}/environment
```

Read-only.

---

# 50. Environment Profile API

```text
GET  /api/v1/environment-profiles
POST /api/v1/environment-profiles
GET  /api/v1/environment-profiles/{profile_id}
PATCH /api/v1/environment-profiles/{profile_id}
GET  /api/v1/environment-profiles/{profile_id}/versions
POST /api/v1/environment-profiles/{profile_id}/versions
GET  /api/v1/environment-profile-versions/{version_id}
```

---

# 51. Runtime Plan

A Runtime Plan is immutable once used by a Preview.

Logical table:

```text
runtime_plans
```

## 51.1 Schema

```json
{
  "id": "runtime-plan-id",
  "project_id": "project-id",
  "version_number": 3,
  "source": {
    "kind": "DETECTED",
    "source_commit": "abc123"
  },
  "environment_profile_version_id": "environment-profile-version-id",
  "services": [
    {
      "key": "web",
      "kind": "APPLICATION",
      "working_directory": ".",
      "build_command": ["npm", "run", "build"],
      "start_command": ["npm", "start"],
      "internal_port": 3000,
      "public": true,
      "health_check": {
        "type": "HTTP",
        "path": "/",
        "timeout_ms": 5000
      },
      "depends_on": [],
      "environment": {},
      "credential_bindings": []
    }
  ],
  "created_at": "...",
  "content_hash": "sha256:..."
}
```

Commands are arrays, not shell strings, unless a future explicitly supported shell mode is added.

This reduces accidental command interpolation and makes intent inspectable.

## 51.2 Service kinds

```text
APPLICATION
BACKGROUND
SUPPORTING
```

Supporting services normally reference curated service definitions rather than arbitrary commands.

## 51.3 Credential binding

```json
{
  "environment_name": "STRIPE_SECRET_KEY",
  "credential_id": "credential-id"
}
```

No secret value appears in the plan.

---

# 52. Runtime Plan API

```text
GET  /api/v1/projects/{project_id}/runtime-plans
POST /api/v1/projects/{project_id}/runtime-plans
GET  /api/v1/runtime-plans/{runtime_plan_id}
```

Creating a Runtime Plan creates an immutable new version.

Request may use:

```json
{
  "mode": "AUTO_DETECT",
  "source_commit": "abc123"
}
```

or explicit supported configuration.

Validation rejects security-prohibited runtime features.

---

# 53. Credential Resource

## 53.1 Schema returned to browser

```json
{
  "id": "credential-id",
  "name": "STRIPE_SECRET_KEY",
  "domain": "PROJECT_RUNTIME",
  "provider": "STRIPE",
  "status": "ACTIVE",
  "active_value_version_id": "credential-value-version-id",
  "validation": {
    "status": "NOT_VALIDATED",
    "checked_at": null
  },
  "assignment_count": 2,
  "created_at": "...",
  "updated_at": "...",
  "version": 4
}
```

## 53.2 Domains

```text
PROJECT_RUNTIME
ENGINE_PROVIDER
INTEGRATION
```

Root/bootstrap and control-plane service secrets are not normal user Credential resources.

## 53.3 Status

```text
ACTIVE
REVOKED
DELETED
INVALID
```

## 53.4 Never-returned fields

The API never returns:

- plaintext secret value;
- ciphertext;
- nonce;
- wrapped DEK;
- KEK ID where exposing it serves no user purpose;
- provider raw Authorization token.

---

# 54. Credential Persistence

Logical tables:

```text
credentials
credential_value_versions
project_credential_assignments
```

## 54.1 Credentials columns

```text
id
owner_id
name
domain
provider
status
active_value_version_id nullable
validation_status
validation_checked_at nullable
created_at
updated_at
version
```

## 54.2 Credential value versions

Server-only:

```text
id
credential_id
ciphertext
nonce
auth_tag nullable
wrapped_dek
key_provider_ref
encryption_version
created_at
revoked_at nullable
```

Never exposed through browser read APIs.

## 54.3 Assignments

```text
id
project_id
credential_id
usage_scope
created_at
created_by
```

Constraint:

```text
unique(project_id, credential_id, usage_scope)
```

`usage_scope` initially:

```text
PROJECT_RUNTIME
```

Provider/integration credentials are assigned through their own configuration semantics rather than pretending they are application runtime secrets.

---

# 55. Credential API

```text
GET    /api/v1/credentials
POST   /api/v1/credentials
GET    /api/v1/credentials/{credential_id}
POST   /api/v1/credentials/{credential_id}/commands/replace
DELETE /api/v1/credentials/{credential_id}

GET    /api/v1/projects/{project_id}/credential-assignments
POST   /api/v1/projects/{project_id}/credential-assignments
DELETE /api/v1/projects/{project_id}/credential-assignments/{assignment_id}
```

## 55.1 Create

Request:

```json
{
  "name": "STRIPE_SECRET_KEY",
  "domain": "PROJECT_RUNTIME",
  "provider": "STRIPE",
  "secret_value": "write-only"
}
```

`secret_value` is write-only.

Response never echoes it.

## 55.2 Replace

```json
{
  "secret_value": "new-write-only-value"
}
```

Returns Command or updated metadata depending on implementation path; the secret is never echoed.

## 55.3 Delete

Requires `If-Match`.

Deletion/revocation semantics follow the Security Design.

---

# 56. Integration Resource

## 56.1 Schema

```json
{
  "id": "integration-id",
  "type": "GITHUB",
  "status": "CONNECTED",
  "display_name": "GitHub",
  "external_account": {
    "installation_id": "provider-installation-id",
    "account_login": "example-org"
  },
  "permissions": [
    "CONTENTS_READ",
    "CONTENTS_WRITE",
    "PULL_REQUEST_WRITE"
  ],
  "created_at": "...",
  "updated_at": "...",
  "version": 2
}
```

## 56.2 Status

```text
CONNECTED
NEEDS_ATTENTION
DISCONNECTED
```

No App private key/installation token is exposed.

---

# 57. GitHub Integration API

Stable product operations:

```text
GET  /api/v1/integrations
GET  /api/v1/integrations/{integration_id}
POST /api/v1/integrations/github/installation-session
GET  /api/v1/integrations/{integration_id}/repositories
POST /api/v1/integrations/{integration_id}/commands/disconnect
```

## 57.1 Installation session

Returns a short-lived browser redirect/installation descriptor:

```json
{
  "authorization_url": "https://github.com/...",
  "expires_at": "..."
}
```

The callback route validates anti-forgery state and persists Integration metadata.

Exact callback path is implementation-specific browser integration plumbing.

## 57.2 Repository list

Returns only repositories authorized to that installation and current principal.

---

# 58. Publish Operation

Publishing is a first-class asynchronous operation because it has external side effects.

Logical table:

```text
publish_operations
```

Schema:

```json
{
  "id": "publish-operation-id",
  "project_id": "project-id",
  "run_id": "run-id",
  "integration_id": "integration-id",
  "source": {
    "git_commit": "def456"
  },
  "target": {
    "repository_id": "provider-repo-id",
    "branch": "kallula/run-15"
  },
  "mode": "OPEN_PULL_REQUEST",
  "state": "QUEUED",
  "external_result": null,
  "failure": null,
  "created_at": "...",
  "completed_at": null
}
```

Modes:

```text
PUSH_BRANCH
OPEN_PULL_REQUEST
```

States:

```text
QUEUED
RUNNING
SUCCEEDED
FAILED
```

API:

```text
POST /api/v1/projects/{project_id}/publish-operations
GET  /api/v1/publish-operations/{id}
```

Trusted Integration Layer performs the remote operation.

---

# 59. Preview Resource

## 59.1 Schema

```json
{
  "id": "preview-id",
  "project_id": "project-id",
  "originating_run_id": "run-id",
  "source": {
    "kind": "COMMIT",
    "git_commit": "abc123",
    "verified_state_id": null
  },
  "runtime_plan_id": "runtime-plan-id",
  "state": "AVAILABLE",
  "route": {
    "available": true,
    "open_url": "/api/v1/previews/preview-id/open"
  },
  "health": {
    "status": "HEALTHY",
    "checked_at": "..."
  },
  "services": [
    {
      "id": "preview-service-id",
      "key": "web",
      "kind": "APPLICATION",
      "public": true,
      "state": "RUNNING",
      "health": "HEALTHY"
    }
  ],
  "out_of_date": false,
  "failure": null,
  "created_at": "...",
  "started_at": "...",
  "stopped_at": null,
  "version": 6
}
```

The API does not return the raw internal host/container URL.

## 59.2 States

```text
NOT_RUNNABLE
STARTING
AVAILABLE
UNAVAILABLE
FAILED
STOPPED
```

## 59.3 Source identity

Preview source is immutable.

If updated to new source, Kallula creates a successor Preview resource rather than mutating the original source identity.

---

# 60. Preview Persistence

Logical tables:

```text
previews
preview_services
```

## 60.1 Preview columns

```text
id
project_id
originating_run_id nullable
source_kind
source_git_commit
verified_state_id nullable
runtime_plan_id
environment_identity_json
state
health_status nullable
failure_class nullable
failure_code nullable
failure_summary nullable
route_key nullable
created_at
started_at nullable
stopped_at nullable
updated_at
version
```

## 60.2 Preview service columns

```text
id
preview_id
service_key
kind
public
state
health_status
runtime_ref server-only nullable
log_stream_id nullable
restart_count
started_at nullable
stopped_at nullable
```

Internal runtime/container IDs are not normally returned.

---

# 61. Preview API

```text
GET  /api/v1/projects/{project_id}/previews
POST /api/v1/projects/{project_id}/previews
GET  /api/v1/previews/{preview_id}
POST /api/v1/previews/{preview_id}/commands/stop
POST /api/v1/previews/{preview_id}/commands/update
GET  /api/v1/previews/{preview_id}/logs
GET  /api/v1/previews/{preview_id}/open
```

## 61.1 Create

Request:

```json
{
  "source": {
    "kind": "LATEST_COMMITTED"
  },
  "runtime_plan_id": "runtime-plan-id"
}
```

or:

```json
{
  "source": {
    "kind": "VERIFIED_STATE",
    "verified_state_id": "verified-state-id"
  }
}
```

Response:

```text
202 Accepted
```

with Preview in `STARTING` or durable creation result plus Command.

## 61.2 Update

`commands/update` request selects new source.

Applying it creates a **new Preview ID** and returns it in Command `result_refs`.

The old Preview remains historical and may be stopped.

## 61.3 Open

```text
GET /api/v1/previews/{preview_id}/open
```

After authorization, returns redirect or short-lived grant exchange to the Preview Gateway.

It never returns Kallula session credentials to generated application code.

---

# 62. Preview Log API

```text
GET /api/v1/previews/{preview_id}/logs
```

Query:

```text
service_id
after_cursor
limit
```

Response:

```json
{
  "items": [
    {
      "timestamp": "...",
      "stream": "STDOUT",
      "message": "Server listening...",
      "truncated": false
    }
  ],
  "next_cursor": "opaque"
}
```

A live log stream may use SSE:

```text
GET /api/v1/previews/{preview_id}/logs/stream
```

This stream is diagnostic and may drop/truncate excessive output according to runtime policy.

It is not the durable Run event journal.

---

# 63. Preview Access Grant

Preview access grant is ephemeral security state.

It is not a general browser-readable list resource.

The `/open` operation may:

- redirect through a one-time token;
- set a Preview-domain scoped cookie;
- establish a short-lived Preview Gateway session.

Persistent database storage is optional and implementation-specific.

If persisted, it must contain:

- opaque grant/session identifier;
- Preview ID;
- principal ID;
- expiry;
- revoked state;

never Kallula control session material.

---

# 64. Knowledge API

Knowledge surfaces normalized read-only entries derived/indexed from engine-native knowledge/evidence.

```text
GET /api/v1/projects/{project_id}/knowledge
GET /api/v1/knowledge/{knowledge_entry_id}
```

Schema:

```json
{
  "id": "knowledge-entry-id",
  "project_id": "project-id",
  "run_id": "run-id",
  "work_item_id": null,
  "category": "DECISION",
  "summary": "Use PostgreSQL for durable application data.",
  "detail": "...",
  "provenance": {
    "artifact_id": "artifact-id",
    "native_ref": null
  },
  "created_at": "..."
}
```

Categories:

```text
INTENT
DECISION
CONSULTATION
PROXY_DECISION
BLOCKER
WORK_ITEM_COMPLETION
LEARNING
OTHER
```

Native engine identifiers may appear only in advanced provenance metadata.

---

# 65. Audit Event

Security/product audit is distinct from Run Event.

Logical table:

```text
audit_events
```

Append-only.

Schema:

```json
{
  "id": "audit-event-id",
  "actor_principal_id": "principal-id",
  "action": "CREDENTIAL_REPLACED",
  "target": {
    "type": "CREDENTIAL",
    "id": "credential-id"
  },
  "project_id": "project-id",
  "run_id": null,
  "outcome": "SUCCESS",
  "reason_code": null,
  "request_id": "req-id",
  "created_at": "...",
  "metadata": {
    "credential_value_version_id": "value-version-id"
  }
}
```

No secret values.

Outcome:

```text
SUCCESS
DENIED
FAILED
```

API availability may be owner/admin only:

```text
GET /api/v1/audit-events
```

with cursor pagination.

---

# 66. Notification Resource

In-app attention/notification delivery is represented independently from Run events.

Logical table:

```text
notifications
```

Schema:

```json
{
  "id": "notification-id",
  "principal_id": "principal-id",
  "project_id": "project-id",
  "run_id": "run-id",
  "type": "RUN_NEEDS_INPUT",
  "title": "Inventory Tool needs your input",
  "status": "UNREAD",
  "deep_link": {
    "resource_type": "INTERACTION",
    "resource_id": "interaction-id"
  },
  "created_at": "...",
  "read_at": null,
  "version": 1
}
```

States:

```text
UNREAD
READ
```

API:

```text
GET   /api/v1/notifications
PATCH /api/v1/notifications/{notification_id}
```

External email/etc delivery records may be separate operational data.

---

# 67. Dashboard Contract

The Dashboard is a projection endpoint rather than the frontend assembling many unrelated calls.

```text
GET /api/v1/dashboard
```

Response:

```json
{
  "needs_attention": [
    {
      "project": { "...summary fields...": true },
      "run": { "...summary fields...": true },
      "attention": {
        "kind": "NEEDS_INPUT",
        "interaction_id": "interaction-id"
      }
    }
  ],
  "active": [],
  "recent": [],
  "generated_at": "..."
}
```

This endpoint is derived.

It does not become the source of truth for Runs/Projects.

Frontend can follow resource IDs to authoritative endpoints.

---

# 68. Project Summary Projection

Project list/dashboard may use a compact summary shape:

```json
{
  "id": "project-id",
  "display_name": "Expense Tracker",
  "workspace_status": "READY",
  "attention": {
    "level": "IN_PROGRESS",
    "label": "Running"
  },
  "current_run": {
    "id": "run-id",
    "control_state": "RUNNING",
    "stage": {
      "category": "EXECUTION",
      "display_label": "Execution"
    }
  },
  "last_verified_state": {
    "id": "verified-state-id",
    "git_commit": "def456"
  },
  "updated_at": "..."
}
```

`attention` is derived and should be recalculable.

It is not independently user-editable state.

---

# 69. Compatibility Resource

Compatibility is part of Engine Installation and Run recovery, but detailed diagnostics have a stable shape.

```json
{
  "launch": {
    "status": "SUPPORTED",
    "reason": null
  },
  "state_format": {
    "status": "SUPPORTED",
    "reason": null
  },
  "resume": {
    "status": "SUPPORTED",
    "reason": null
  },
  "security": {
    "status": "SUPPORTED",
    "reason": null
  },
  "runtime": {
    "status": "SUPPORTED",
    "reason": null
  }
}
```

Run-specific resume check:

```text
GET /api/v1/runs/{run_id}/resume-compatibility
```

Response includes:

- pinned engine;
- pinned environment;
- available engine/runtime;
- status;
- reason;
- allowed action.

This is read-only.

---

# 70. Log Stream Metadata

A logical `log_streams` metadata record may represent:

- Execution Attempt diagnostics;
- Preview service runtime logs;
- Preview build logs.

Fields:

```text
id
owner_type
owner_id
log_class
storage_ref
created_at
closed_at nullable
truncated boolean
retention_expires_at nullable
```

Raw log storage is not required to be in the control database.

---

# 71. Runtime Failure Object

Runtime/engine/integration failures use a common embedded shape where useful:

```json
{
  "class": "PREVIEW_HEALTH_FAILED",
  "code": "HTTP_HEALTHCHECK_FAILED",
  "summary": "The application did not become healthy before the startup deadline.",
  "recoverability": "RETRYABLE_AS_NEW_OPERATION",
  "artifact_ids": ["artifact-id"],
  "occurred_at": "..."
}
```

No raw stack trace is required in normal user-facing API.

Advanced diagnostic artifacts may contain sanitized details.

---

# 72. Command Persistence

Logical table:

```text
commands
```

Columns:

```text
id
actor_principal_id
command_type
target_type
target_id
state
request_json
request_hash
idempotency_key
created_at
processing_at nullable
applied_at nullable
failed_at nullable
failure_code nullable
failure_summary nullable
result_refs_json
request_id
```

Constraints include idempotency uniqueness by scoped key.

Command request JSON must never persist plaintext credential values.

Credential create/replace requires a specialized path where the secret is encrypted before durable command metadata is written.

---

# 73. Idempotency Persistence

Logical table:

```text
idempotency_records
```

Fields:

```text
principal_id
method
canonical_path
idempotency_key
request_hash
response_status
response_resource_ref
response_snapshot_json nullable
created_at
expires_at
```

Security-sensitive response snapshots exclude write-only secret inputs.

---

# 74. Engine Adapter Ingestion Contract

This is an internal Kallula contract, not a public browser endpoint.

The adapter reports normalized signals such as:

```text
stage_changed
work_item_changed
interaction_opened
artifact_discovered
test_result
verification_result
semantic_outcome
```

Each signal contains:

- Run ID;
- Attempt ID;
- attempt-local source sequence;
- normalized payload;
- optional native diagnostics.

Control Plane ingestion:

1. authenticates/trusts worker channel;
2. deduplicates `(attempt_id, source_sequence)`;
3. allocates next Run event `sequence`;
4. persists Event;
5. updates affected projection atomically where required;
6. publishes live notification after commit.

Native Siesta output never bypasses this normalization into product state.

---

# 75. Runtime Manager Internal Contract

Internal requests use normalized specs, not raw browser input.

Worker launch spec references:

```text
run_id
attempt_id
workspace_id
run_engine_runtime_id
engine_installation_id
environment_snapshot_id
resource_policy
network_policy
secret/provider grant descriptors
```

It does not accept:

- arbitrary host mount path from browser;
- privileged flag;
- raw runtime socket;
- unvalidated container CLI fragments.

Preview launch references:

```text
preview_id
source_snapshot_ref
runtime_plan_id
service specs
credential binding grants
network policy
```

The exact internal transport is not fixed by this document.

---

# 76. Run Engine Runtime Reference

Logical table:

```text
run_engine_runtimes
```

Fields:

```text
id
run_id unique
storage_driver
storage_key
state
created_at
validated_at nullable
metadata_json
```

Browser API does not return physical `storage_key`.

Run configuration/diagnostics may expose:

```json
{
  "engine_runtime": {
    "status": "READY"
  }
}
```

---

# 77. Preview Source Snapshot Reference

Logical metadata:

```text
preview_source_snapshots
```

Fields:

```text
id
preview_id unique
project_id
git_commit
storage_driver
storage_key
content_hash nullable
created_at
deleted_at nullable
```

Physical storage is server-only.

The API exposes `git_commit`, not the storage path.

---

# 78. Relationship Summary

```text
Project
|
+-- Workspace
|
+-- Run *
|   |
|   +-- Run Config Snapshot
|   +-- Environment Snapshot
|   +-- Run Engine Runtime
|   +-- Execution Attempt *
|   +-- Command *
|   +-- Pending Interaction *
|   +-- Work Item *
|   +-- Event *
|   +-- Artifact *
|   +-- Verification Result *
|   +-- Verified State *
|
+-- Runtime Plan *
+-- Preview *
+-- Credential Assignment *
+-- Publish Operation *
```


```text
Principal
  └─ owns Project *
       ├─ Workspace 1
       ├─ Run *
       │   ├─ RunConfigSnapshot 1
       │   ├─ EnvironmentSnapshot 1
       │   ├─ RunEngineRuntime 1
       │   ├─ ExecutionAttempt *
       │   ├─ Command *
       │   ├─ PendingInteraction *
       │   │    └─ InteractionResponse 0..1
       │   ├─ WorkItem *
       │   ├─ Event *
       │   ├─ Artifact *
       │   ├─ VerificationResult *
       │   └─ VerifiedState 0..*
       │
       ├─ RuntimePlan *
       ├─ Preview *
       │    ├─ PreviewSourceSnapshot 1
       │    └─ PreviewService *
       │
       ├─ CredentialAssignment *
       └─ PublishOperation *
```

Global/reusable resources:

```text
AgentProfile -> AgentProfileVersion *
EnvironmentProfile -> EnvironmentProfileVersion *
EngineInstallation *
Credential *
Integration *
AuditEvent *
Notification *
```

---

# 79. Referential Integrity Rules

Correctness-critical references:

- Run belongs to existing Project.
- Attempt belongs to Run.
- Run Config Snapshot belongs to exactly one Run.
- Environment Snapshot belongs to exactly one Run.
- Run Engine Runtime belongs to exactly one Run.
- Interaction belongs to Run.
- Work Item belongs to Run.
- Run Event belongs to Run.
- Verified State's verification result belongs to same Run.
- Verified State's Project matches Run's Project.
- Preview Project matches referenced Verified State/Runtime Plan Project.
- Runtime Plan Project matches Preview Project.
- Credential assignment Project/Credential are owner-accessible and domain-compatible.
- active Project pointers reference resources belonging to that Project.

Database foreign keys should enforce these where practical.

---

# 80. Uniqueness and Invariant Constraints

At minimum:

```text
unique(project_id, run.ordinal)
unique(run_id, attempt.ordinal)
unique(run_id, event.sequence)
unique(attempt_id, event.source_event_sequence) where source sequence exists
unique(run_id) for RunConfigSnapshot
unique(run_id) for EnvironmentSnapshot
unique(run_id) for RunEngineRuntime
unique(project_id) for active execution lease
unique(interaction_id) for accepted InteractionResponse
unique(project_id, credential_id, usage_scope) for CredentialAssignment
unique(profile_id, version_number) for AgentProfileVersion
unique(environment_profile_id, version_number) for EnvironmentProfileVersion
unique(project_id, runtime_plan.version_number)
```

v1 also enforces at most one `OPEN` Pending Interaction per Run.

---

# 81. Transaction Boundaries

The following operations require atomic durable boundaries.

## 81.1 Command acceptance

Atomically:

- authorize;
- validate target state;
- persist Command;
- apply immediate control-state mutation if defined;
- write Audit/Event as required.

## 81.2 Interaction response

Atomically:

- verify interaction still `OPEN`;
- insert response;
- resolve interaction;
- clear/update Run pending interaction pointer;
- persist Command/Event;
- move Run to `QUEUED` when a new Attempt is required.

## 81.3 Engine event ingestion

When an event changes product projection:

- deduplicate source signal;
- allocate event sequence;
- persist Event;
- update projection;
- commit;
- publish live notice.

## 81.4 Verified State

Atomically:

- persist successful Verification Result;
- create Verified State;
- update Project current verified pointer if applicable;
- create Event.

---

# 82. Derived Data Policy

The following may be recomputed:

- Dashboard sections;
- attention labels;
- Work Item counts on Run summary;
- Project current attention;
- Preview `out_of_date`;
- “current equals verified” indicator;
- compatibility display summaries.

Derived fields may be cached.

They are not independent sources of truth.

---

# 83. Soft Delete and Retention

Not every resource needs user-facing deletion in v1.

Where deletion exists:

- Credentials follow security deletion/revocation;
- Preview runtime resources can be destroyed while metadata remains;
- exports may expire;
- logs may expire;
- Project deletion is deferred unless explicitly implemented.

Do not overload `deleted_at` across every table preemptively.

Retention policy may archive/delete logs/artifacts without rewriting Run state.

---

# 84. Security-Sensitive Never-Returned Data

No normal browser API may return:

```text
credential plaintext
credential ciphertext
DEKs
KEKs/root keys
session secret/hash
CSRF server secret
GitHub App private key
GitHub installation access token
provider raw API token
control DB credentials
runtime-manager/container socket credentials
physical workspace host path
Run Engine Runtime host path
Preview source physical path
internal network credentials
raw Authorization/Cookie headers
```

These omissions are part of the contract, not UI discretion.

---

# 85. Write-Only Fields

Fields accepted in requests but never echoed:

```text
credential.secret_value
credential_replace.secret_value
authentication provider callback secrets
future bootstrap secret inputs
```

OpenAPI/schema tooling should mark them `writeOnly` where supported.

---

# 86. Sensitive Log/API Rules

API middleware must not log:

- request bodies for Credential create/replace;
- cookies;
- Authorization headers;
- Preview one-time grants;
- provider callback secrets.

Problem responses never echo write-only inputs.

---

# 87. Native Diagnostics

Advanced diagnostics may expose a constrained object:

```json
{
  "engine": {
    "native_stage_id": "phase-3",
    "adapter_version": "1.0.0",
    "engine_revision": "20b149e..."
  }
}
```

Rules:

- optional;
- read-only;
- never required by normal frontend flow;
- never used as stable control input;
- no physical server paths/secrets.

There is no public endpoint such as:

```text
POST /siesta/stop-md
```

or any other native-mechanism action.

---

# 88. Health and Readiness

Platform operational endpoints are separate from authenticated product APIs.

Examples:

```text
/health/live
/health/ready
```

They return minimal information.

They do not expose:

- DB credentials;
- engine secrets;
- Project state;
- internal topology.

Deep diagnostics require authenticated operator tooling.

---

# 89. Rate Limits

Rate limiting is an implementation/operations concern, but API behavior must be stable.

When throttled:

```text
429 Too Many Requests
code = RATE_LIMITED
```

Response may include:

```text
Retry-After
```

Rate limits must not be so aggressive that ordinary SSE reconnect or event replay becomes unreliable.

Credential/auth endpoints may use stricter policies.

---

# 90. SSE Authorization and Session Expiry

SSE uses normal authenticated browser session.

If session expires:

- stream closes/returns authentication failure;
- frontend reauthenticates;
- on return, it replays from last durable sequence.

No execution state is lost.

SSE stream itself never carries reusable secret material.

---

# 91. API Caching

Authenticated mutable resource responses should default to private/no-store or revalidation-safe behavior appropriate to the implementation.

Security-sensitive endpoints:

- session;
- credentials;
- integrations;
- Preview open/grant operations;

must not be cached by shared intermediaries.

Immutable artifact/download responses may use content-hash caching if authorization remains enforced.

---

# 92. Content Size and Streaming

The API avoids loading unbounded content into JSON.

Stream or bound:

- file raw content;
- artifacts;
- source exports;
- logs;
- large diffs.

Text JSON endpoints must have configured size bounds and explicit truncation metadata.

Example:

```json
{
  "content": "...",
  "truncated": true,
  "total_size_bytes": 928173
}
```

---

# 93. Database Storage Categories

The logical persistence model separates:

## 93.1 Relational/control state

- Principals
- Projects
- Runs
- Attempts
- Commands
- Interactions
- Work Items
- Events metadata/payloads
- Profiles/versions
- Credentials metadata/ciphertext
- Engine Installations
- Environment Snapshots
- Runtime Plans
- Verification/Verified States
- Preview metadata
- Integrations
- Audit Events
- Notifications

## 93.2 Canonical workspace storage

- source;
- Git;
- engine Project-native state/evidence.

## 93.3 Run Engine Runtime storage

- Run-scoped mutable engine runtime.

## 93.4 Blob/log/export storage

- large artifacts;
- runtime logs;
- exports;
- optional event raw evidence.

The DB may reference these through opaque storage keys that never enter normal browser APIs.

---

# 94. Schema Migration Rules

Database migrations must preserve:

- stable IDs;
- Run control history;
- event sequence;
- credential encryption metadata;
- Engine/Environment pinning;
- Verified State source identity;
- audit history.

A schema migration must not silently reinterpret historical enum values.

If an enum evolves:

- existing stored values retain meaning;
- migration is explicit;
- API compatibility is tested.

---

# 95. API Compatibility Rules

Backward-compatible changes may include:

- optional response field;
- new endpoint;
- new event type;
- new optional Event payload field;
- new enum values in fields explicitly documented as extensible.

Potential breaking changes:

- renaming/removing field;
- changing field type;
- changing state meaning;
- changing command semantics;
- changing ordering/pagination behavior;
- reusing an enum value with new meaning;
- exposing previously hidden native engine mechanics as required inputs.

Breaking changes require version/migration strategy.

---

# 96. Event Payload Versioning

Each Event includes:

```text
payload_version
```

`event_type + payload_version` determines typed payload interpretation.

Adding new optional payload keys does not need incrementing version.

Changing required meaning/shape does.

Frontend must always be able to fall back to Event `summary`.

---

# 97. Capability Evolution

Frontend does not infer capability support from engine revision string.

It reads:

- product version capabilities;
- Engine Installation capability manifest;
- current resource state.

API actions still enforce capability server-side even if the frontend incorrectly renders a control.

Unsupported action returns:

```text
409 or 422
CAPABILITY_UNSUPPORTED
```

depending on whether conflict is state versus configuration.

---

# 98. Example — Interactive Run Flow

```text
POST /projects
  -> Project + initial Run

GET /runs/{id}
  -> STARTING

GET /runs/{id}/events/stream
  -> RUN_STARTED
  -> STAGE_STARTED REQUIREMENTS
  -> INTERACTION_OPENED

GET /interactions/{id}
  -> OPEN

POST /interactions/{id}/commands/respond
  -> Command ACCEPTED/APPLIED

GET /runs/{id}
  -> QUEUED
     or RUNNING depending continuation path

SSE
  -> ATTEMPT_STARTED
  -> INTERACTION_RESOLVED
  -> STAGE_COMPLETED
```

The browser does not need to know whether the original worker exited during the wait.

---

# 99. Example — Safe Stop Flow

```text
POST /runs/{id}/commands/stop
  -> 202 Command ACCEPTED

Run:
RUNNING -> STOP_REQUESTED

SSE:
RUN_STOP_REQUESTED

... engine keeps working until safe boundary ...

Attempt:
ACTIVE -> EXITED

Run:
STOP_REQUESTED -> STOPPED

SSE:
RUN_STOPPED
```

Command acceptance is not stop confirmation.

---

# 100. Example — Resume Flow

```text
GET /runs/{id}/resume-compatibility
  -> SUPPORTED

POST /runs/{id}/commands/resume
  -> Command

Run:
STOPPED -> QUEUED

Coordinator:
new Attempt ordinal = previous + 1

Run:
STARTING -> RUNNING
```

Same Run ID.

Same canonical Workspace.

Same Run Engine Runtime.

New Execution Attempt ID.

---

# 101. Example — Preview Flow

```text
POST /projects/{id}/runtime-plans
  -> RuntimePlan v3

POST /projects/{id}/previews
  source = latest committed
  runtime_plan_id = v3
  -> Preview STARTING

Preview source:
commit abc123

Build:
no Project runtime secrets

Runtime:
inject credential bindings to target services only

Health:
passes

Preview:
AVAILABLE

GET /previews/{id}/open
  -> scoped Preview access exchange/redirect
```

A newer Project commit does not mutate this Preview's source.

---

# 102. Example — Credential Flow

```text
POST /credentials
{
  name,
  domain,
  secret_value
}
```

Server:

```text
authorize
encrypt immediately
persist ciphertext/value-version
persist metadata
audit
discard request plaintext
```

Response:

```json
{
  "id": "...",
  "name": "STRIPE_SECRET_KEY",
  "domain": "PROJECT_RUNTIME",
  "status": "ACTIVE"
}
```

No value.

Assignment:

```text
POST /projects/{id}/credential-assignments
```

Runtime Plan refers to Credential ID.

Preview launcher resolves/decrypts only for authorized target service.

---

# 103. HTTP Status Summary

Common successful statuses:

```text
200 OK              read/update completed
201 Created         resource durably created
202 Accepted        asynchronous/durable command accepted
204 No Content      successful deletion/unassignment where no body needed
```

Common errors:

```text
400 malformed request
401 unauthenticated
403 explicitly forbidden operation where non-disclosure is not required
404 not found/not visible
409 state/idempotency/business conflict
410 replay cursor expired / expired resource
412 stale If-Match
422 semantically invalid configuration
428 missing required If-Match
429 rate limited
500 unexpected internal failure
503 required dependency unavailable
```

---

# 104. Initial Endpoint Inventory

## Session

```text
GET  /session
POST /session/logout
```

## Dashboard

```text
GET /dashboard
GET /stream
```

## Projects

```text
GET  /projects
POST /projects
GET  /projects/{project_id}
PATCH /projects/{project_id}
```

## Runs

```text
GET  /projects/{project_id}/runs
POST /projects/{project_id}/runs
GET  /runs/{run_id}
GET  /runs/{run_id}/configuration
GET  /runs/{run_id}/environment
GET  /runs/{run_id}/resume-compatibility
POST /runs/{run_id}/commands/stop
POST /runs/{run_id}/commands/resume
```

## Attempts

```text
GET /runs/{run_id}/attempts
GET /execution-attempts/{attempt_id}
```

## Commands

```text
GET /commands/{command_id}
```

## Interactions

```text
GET  /interactions
GET  /interactions/{interaction_id}
POST /interactions/{interaction_id}/commands/respond
```

## Work Items

```text
GET /runs/{run_id}/work-items
GET /work-items/{work_item_id}
```

## Events

```text
GET /runs/{run_id}/events
GET /runs/{run_id}/events/stream
```

## Artifacts

```text
GET /runs/{run_id}/artifacts
GET /artifacts/{artifact_id}
GET /artifacts/{artifact_id}/content
```

## Verification

```text
GET /projects/{project_id}/verified-states
GET /verified-states/{verified_state_id}
```

## Files

```text
GET /projects/{project_id}/files
GET /projects/{project_id}/files/content
GET /projects/{project_id}/files/raw
```

## Git

```text
GET /projects/{project_id}/git/status
GET /projects/{project_id}/git/commits
GET /projects/{project_id}/git/commits/{sha}
GET /projects/{project_id}/git/diff
```

## Exports

```text
POST /projects/{project_id}/exports
GET  /exports/{export_id}
GET  /exports/{export_id}/download
```

## Engines

```text
GET /engine-installations
GET /engine-installations/{id}
```

## Agent Profiles

```text
GET  /agent-profiles
POST /agent-profiles
GET  /agent-profiles/{id}
PATCH /agent-profiles/{id}
GET  /agent-profiles/{id}/versions
POST /agent-profiles/{id}/versions
GET  /agent-profile-versions/{id}
```

## Environment Profiles

```text
GET  /environment-profiles
POST /environment-profiles
GET  /environment-profiles/{id}
PATCH /environment-profiles/{id}
GET  /environment-profiles/{id}/versions
POST /environment-profiles/{id}/versions
GET  /environment-profile-versions/{id}
```

## Runtime Plans

```text
GET  /projects/{project_id}/runtime-plans
POST /projects/{project_id}/runtime-plans
GET  /runtime-plans/{id}
```

## Credentials

```text
GET    /credentials
POST   /credentials
GET    /credentials/{id}
POST   /credentials/{id}/commands/replace
DELETE /credentials/{id}

GET    /projects/{project_id}/credential-assignments
POST   /projects/{project_id}/credential-assignments
DELETE /projects/{project_id}/credential-assignments/{id}
```

## Integrations

```text
GET  /integrations
GET  /integrations/{id}
POST /integrations/github/installation-session
GET  /integrations/{id}/repositories
POST /integrations/{id}/commands/disconnect
```

## Publish

```text
POST /projects/{project_id}/publish-operations
GET  /publish-operations/{id}
```

## Previews

```text
GET  /projects/{project_id}/previews
POST /projects/{project_id}/previews
GET  /previews/{id}
POST /previews/{id}/commands/stop
POST /previews/{id}/commands/update
GET  /previews/{id}/logs
GET  /previews/{id}/logs/stream
GET  /previews/{id}/open
```

## Knowledge

```text
GET /projects/{project_id}/knowledge
GET /knowledge/{id}
```

## Notifications

```text
GET   /notifications
PATCH /notifications/{id}
```

## Audit

```text
GET /audit-events
```

All paths above are relative to `/api/v1`.

---

# 105. API Fields That Are Projections, Not Authority

The frontend may receive convenient projections such as:

```text
Project.attention
Project.current_run
Run.work_item_summary
Run.stage
Preview.out_of_date
Dashboard.needs_attention
Credential.assignment_count
```

The API implementation must recompute these from authoritative records.

Clients must not send them back as mutable fields.

---

# 106. Data Ownership Boundaries

## Kallula DB owns

- resource IDs;
- ownership;
- Run/Attempt state;
- Commands;
- Pending Interactions;
- normalized Events;
- profiles/snapshots;
- credential metadata/ciphertext;
- Preview metadata;
- audit.

## Workspace owns

- source/Git;
- current working tree;
- engine-native Project checkpoint/evidence.

## Run Engine Runtime owns

- Run-scoped mutable engine runtime state.

## External integration owns

- GitHub repository remote state;
- provider account/token validity.

## Runtime backend owns transiently

- container/process state;
- Preview service runtime state.

Kallula stores references/projections for external/transient state.

---

# 107. Data Reconciliation Rules

If sources disagree:

## Run DB says RUNNING, worker missing

Do not set `COMPLETED`.

Reconciler examines engine/workspace evidence.

## Event projection differs from canonical Run record

Canonical Run record plus reconciliation wins; corrective event may be appended.

## Preview DB says AVAILABLE, service missing

Preview becomes `UNAVAILABLE`/`FAILED` according to reconciler evidence.

## Project current verified pointer differs from verification history

Only Verified State creation rules may repair pointer.

## Git status differs from cached summary

Canonical workspace Git wins.

---

# 108. API Acceptance Criteria

## AC-API-001 — Opaque IDs

Clients can operate without parsing Kallula resource IDs.

## AC-API-002 — Stable Run state

Run API exposes the exact eight control states defined by architecture and does not replace them with engine phases.

## AC-API-003 — Stage separation

Run state and Stage are separate fields.

## AC-API-004 — Attempt separation

A resumed Run can return multiple Execution Attempts under one unchanged Run ID.

## AC-API-005 — Durable command distinction

Safe-stop command can be `APPLIED` while Run remains `STOP_REQUESTED`; API does not equate command application with final Run outcome.

## AC-API-006 — Command idempotency

Retrying the same stop/respond/resume request with the same idempotency key does not create duplicate control effects.

## AC-API-007 — Idempotency mismatch

Reusing an idempotency key with a different payload fails explicitly.

## AC-API-008 — Stale mutation protection

A stale profile/project/credential metadata update using an old ETag fails rather than overwriting newer state.

## AC-API-009 — Durable interaction

An OPEN interaction survives browser disconnect and can be fetched from another session/device.

## AC-API-010 — Single interaction response

Two different responses cannot both become accepted for one Pending Interaction.

## AC-API-011 — Event ordering

Every Run Event has a unique monotonic `sequence`.

## AC-API-012 — Adapter event deduplication

Re-delivery of the same `(attempt_id, source_event_sequence)` does not append a duplicate normalized event.

## AC-API-013 — SSE replay

A client reconnecting after event sequence N receives durable events after N before live events.

## AC-API-014 — SSE not source of truth

Losing SSE connection does not change Run/Preview state.

## AC-API-015 — Unknown event survivability

Frontend can show an Event summary even if it does not understand a newly added `event_type`.

## AC-API-016 — Verified source exactness

Verified State API always contains an exact source identity/commit and Verification Result.

## AC-API-017 — Preview source immutability

Preview API source identity never changes after Preview creation.

## AC-API-018 — Preview update identity

Updating Preview to a new source produces a new Preview ID/successor rather than rewriting historical source attribution.

## AC-API-019 — Preview does not verify

Preview state transition to `AVAILABLE` does not alter Verified State.

## AC-API-020 — Secret never returned

Credential create/replace/read/list responses never return plaintext or encrypted secret material.

## AC-API-021 — Secret not in Run snapshot

Run configuration contains permitted Credential IDs/names only.

## AC-API-022 — Runtime Plan secret alias only

Runtime Plan contains credential references/aliases, never plaintext.

## AC-API-023 — GitHub token isolation

Integration APIs expose metadata/permissions but never GitHub App private keys or installation tokens.

## AC-API-024 — Workspace path isolation

Normal API responses never expose physical host workspace/Run Engine Runtime paths.

## AC-API-025 — Read-only Files v1

No v1 Files endpoint mutates Project source.

## AC-API-026 — Source selector clarity

Files/Preview/export endpoints identify the exact current/verified/commit source selected.

## AC-API-027 — Project creation partial truth

If Project creation succeeds but the initial Run later fails to start, Project remains retrievable and Run truthfully reports failure.

## AC-API-028 — Capability server enforcement

Submitting an unsupported engine action fails server-side even if a frontend mistakenly renders the control.

## AC-API-029 — Resume incompatibility

Resume endpoint cannot force continuation when resume compatibility is unsupported/unknown.

## AC-API-030 — One Project writer

Concurrent start/resume operations cannot create two valid Project execution leases.

## AC-API-031 — Audit secret safety

Audit API contains IDs/metadata, never credential values.

## AC-API-032 — Problem safety

Error responses do not echo secret inputs or raw auth headers.

## AC-API-033 — Large content bounded

Large file/log/diff responses use streaming or explicit truncation rather than unbounded JSON.

## AC-API-034 — Resource ownership

Supplying another principal's resource ID does not bypass authorization.

## AC-API-035 — Historical config immutability

Run configuration, Environment Snapshot, Agent Profile Version, Verified State, and Verification Result cannot be patched after creation.

## AC-API-036 — Engine-native containment

No normal action requires clients to send Siesta phase IDs, `stop.md`, checkpoint paths, or native artifact filenames.

## AC-API-037 — Account stream is projection

Missing an account-level `resource_changed` stream message can be repaired by refetch; it is never the only durable state record.

## AC-API-038 — Event commit before publish

Live Event delivery occurs only after the Event/projection transaction is durably committed.

## AC-API-039 — Credential write-only schema

Generated API/OpenAPI representation marks secret-value inputs write-only and omits them from output schemas.

## AC-API-040 — API version isolation

A future breaking schema change cannot silently alter `/api/v1` semantics.

---

# 109. PRD Traceability

| PRD area | API/data resolution |
|---|---|
| Project lifecycle | §§17–19 |
| Run lifecycle | §§20–25 |
| Human interaction | §§26–28 |
| Work Items | §30 |
| Activity/events | §§31–36 |
| Artifacts/files/Git | §§37–43 |
| Verification/current state | §§39–40 |
| Agent configuration | §§44–47 |
| Environment | §§48–52 |
| Credentials | §§53–55 |
| GitHub/integrations | §§56–58 |
| Preview | §§59–63 |
| Knowledge/provenance | §§64, 37–40 |
| Run history | Runs/Attempts immutable history |
| Notifications | §66 |
| Auditing | §65 |
| Reproducibility | §§22, 44–52 |
| API/nonfunctional correctness | §§4–15, 79–97 |

---

# 110. Architecture Traceability

| Architecture area | Contract |
|---|---|
| Project | §§17–19 |
| Run | §§20–22 |
| Execution Attempt | §23 |
| execution lease | §24 |
| Run state machine | §§20, 25 |
| human interaction | §§26–28 |
| stage | §29 |
| Event Journal | §§31–36 |
| Artifact Index | §§37–38 |
| Verified State | §§39–40 |
| durable commands | §§15, 25, 72 |
| reconciliation | §§107, 81 |
| Engine Installation | §§44–45 |
| configuration snapshot | §22 |
| live updates | §§35–36 |
| trust boundaries | §§53–58, 84–86 |

---

# 111. Siesta Adaptation Traceability

| Adaptation area | Contract |
|---|---|
| normalized stages | §29 |
| Work Item mapping | §30 |
| structured events | §§31–33, 74 |
| source event identity | §31.3 |
| Phase 0 durable interaction | §§26–28 |
| semantic outcome | Run/Attempt state + events |
| safe stop | §25.1 |
| resume | §25.2 |
| artifacts | §§37–38 |
| Agent Slots | §§45–47 |
| capability manifest | §45 |
| native diagnostics containment | §87 |

---

# 112. UX Traceability

| UX surface | API contract |
|---|---|
| Dashboard | §§67–68 |
| Projects | §§17–18 |
| Create Project | §18.2 |
| Interview | §§26–28 |
| Current Run | §§20–25 |
| Work Items | §30 |
| Activity | §§31–36 |
| Tests/Verification | §§39–40 |
| Files | §41 |
| Git | §42 |
| Preview | §§59–63 |
| Runtime Logs | §62 |
| Agents | §§46–47 |
| Environment | §§48–52 |
| Credentials | §§53–55 |
| Knowledge | §64 |
| History/Attempts | §§20, 23 |
| Engine/System | §§44–45, 69 |

---

# 113. Security Traceability

| Security area | API/data enforcement |
|---|---|
| browser session | §§10–11 |
| object authorization | §11 |
| no secret reveal | §§53–55, 84–86 |
| envelope encryption metadata | §54 |
| Project credential assignment | §§54–55 |
| GitHub token isolation | §§56–58 |
| Preview access separation | §§61–63 |
| audit | §65 |
| error redaction | §§13, 86 |
| host path secrecy | §§19, 76–77, 84 |
| security failure codes | §§13–14, 71 |

---

# 114. Execution Environment Traceability

| Runtime area | Contract |
|---|---|
| Workspace identity | §19 |
| Run Engine Runtime | §76 |
| Environment Snapshot | §49 |
| Runtime Plan | §§51–52 |
| Preview source snapshot | §§59, 77 |
| Preview service records | §§59–62 |
| runtime logs | §§62, 70 |
| runtime failure classes | §71 |
| runtime manager normalized specs | §75 |
| immutable source | §§41, 59–61 |
| runtime credentials | §§51, 53–55 |

---

# 115. Deliberately Open Implementation Decisions

This contract intentionally leaves these choices to implementation:

1. exact server framework;
2. exact relational database engine;
3. ORM/query layer;
4. exact internal queue/wakeup mechanism for Commands;
5. exact transaction/isolation implementation;
6. exact SSE broker/fan-out implementation;
7. exact object/log storage backend;
8. exact OpenAPI generation tooling;
9. exact ID implementation behind opaque strings;
10. exact account-stream cursor encoding;
11. exact cache implementation;
12. exact database indexes beyond correctness constraints;
13. exact Git library/CLI strategy;
14. exact authentication provider callback routes;
15. exact Preview access-grant cryptographic format;
16. exact retention durations;
17. exact admin/operator API surface;
18. exact internal Runtime Manager/adapter transport.

These choices must implement this contract, not redefine it.

---

# 116. Implementation Status

The implementation plan now exists:

> [`Kallula — Implementation Plan.md`](./Kallula%20%E2%80%94%20Implementation%20Plan.md)

Use that document to sequence development and select the first-release implementation choices.

No more architecture document is required before coding starts.

The **Test & Compatibility Strategy** is still required before release. It is intentionally deferred until the implementation has real testable seams, runtime behavior, and compatibility fixtures.


# Appendix A — Logical Table Inventory

```text
principals
projects
workspaces

runs
run_config_snapshots
run_engine_runtimes
execution_attempts
project_execution_leases
commands
idempotency_records

pending_interactions
interaction_responses
work_items
events
artifacts
verification_results
verified_states

engine_installations

agent_profiles
agent_profile_versions
environment_profiles
environment_profile_versions
environment_snapshots
runtime_plans

credentials
credential_value_versions
project_credential_assignments

integrations
publish_operations

previews
preview_source_snapshots
preview_services
log_streams

notifications
audit_events
exports
```

This is the canonical logical model. Physical decomposition may differ only if the same constraints/semantics are preserved.

---

# Appendix B — Mutability Matrix

| Resource | User mutable? | Server state evolves? | Immutable history? |
|---|---:|---:|---:|
| Project | Yes, limited defaults/metadata | Yes | Run history separate |
| Workspace | No | Yes | source/Git history |
| Run | No direct PATCH | Yes | Yes after terminal |
| Run Config Snapshot | No | No | Yes |
| Environment Snapshot | No | No | Yes |
| Execution Attempt | No | Yes | Yes after end |
| Command | No | Yes to terminal command state | Yes |
| Pending Interaction | Response only via command | Yes | Yes after resolution |
| Interaction Response | No | No | Yes |
| Work Item | No | Yes via engine projection | Yes through events |
| Event | No | No | Yes |
| Artifact metadata | No | Maybe retention metadata | Yes |
| Verification Result | No | No | Yes |
| Verified State | No | No | Yes |
| Agent Profile | Metadata | Yes | versions immutable |
| Agent Profile Version | No | No | Yes |
| Environment Profile | Metadata | Yes | versions immutable |
| Environment Profile Version | No | No | Yes |
| Runtime Plan | No after creation | No | Yes |
| Credential | Metadata/status | Yes | value versions hidden |
| Credential Value Version | No browser read | Server lifecycle | Yes/audited |
| Integration | Commands only | Yes | Audit history |
| Preview | Commands only | Yes | Yes after stop/fail |
| Preview Source Snapshot | No | Cleanup metadata | Source identity immutable |
| Audit Event | No | No | Yes |
| Notification | Read state | Yes | Yes |

---

# Appendix C — State Enums

## Run

```text
QUEUED
STARTING
RUNNING
WAITING_FOR_HUMAN
STOP_REQUESTED
STOPPED
FAILED
COMPLETED
```

## Execution Attempt

```text
ALLOCATED
STARTING
ACTIVE
SUSPENDED
EXITED
LOST
```

## Command

```text
ACCEPTED
PROCESSING
APPLIED
FAILED
```

## Interaction

```text
OPEN
ANSWERED
DELEGATED
CANCELED
SUPERSEDED
```

## Work Item

```text
PENDING
ACTIVE
COMPLETED
BLOCKED
SKIPPED
UNKNOWN
```

## Verification

```text
PASSED
FAILED
INCONCLUSIVE
```

## Preview

```text
NOT_RUNNABLE
STARTING
AVAILABLE
UNAVAILABLE
FAILED
STOPPED
```

## Preview service

```text
PENDING
STARTING
RUNNING
UNHEALTHY
EXITED
FAILED
STOPPED
```

## Engine Installation

```text
CANDIDATE
SUPPORTED
DEPRECATED
BLOCKED
```

## Compatibility

```text
SUPPORTED
UNSUPPORTED
UNKNOWN
```

---

# Appendix D — API Correctness Invariants

1. IDs are opaque and stable.
2. Resource versions increase monotonically on mutation.
3. Run state and Stage are independent.
4. A Run can have many Attempts.
5. Only one Project execution lease is valid at a time.
6. A terminal completed Run never restarts.
7. A safe-stop command does not imply stopped state.
8. A pending interaction has at most one accepted response.
9. Event sequence is monotonic per Run.
10. Adapter event ingestion is idempotent per Attempt source sequence.
11. Event publication occurs after persistence.
12. Verified State always points to exact source and successful verification.
13. Preview source identity is immutable.
14. Preview availability does not imply verification.
15. Runtime Plans contain secret references, not values.
16. Credential read APIs never reveal values.
17. GitHub integration APIs never reveal access tokens.
18. Physical storage paths are server-only.
19. Historical Run/config/evidence resources are immutable.
20. Siesta-native mechanics stay behind the adapter.
21. Live streams are delivery paths, never sole state.
22. Derived dashboard/attention fields can be rebuilt from authoritative records.
23. Unknown execution failure never becomes success by default.
24. Incompatible resume fails closed.
25. Browser Files API is read-only in v1.

---

# Appendix E — Recommended OpenAPI Organization

When implementation begins, generate one versioned OpenAPI document grouped by tags:

```text
Session
Dashboard
Projects
Runs
Attempts
Commands
Interactions
WorkItems
Events
Artifacts
Verification
Files
Git
Exports
Engines
AgentProfiles
EnvironmentProfiles
RuntimePlans
Credentials
Integrations
Publishing
Previews
Knowledge
Notifications
Audit
```

The OpenAPI document is generated from/validated against this normative contract.

OpenAPI is an implementation artifact; this specification remains the source of behavioral semantics until superseded deliberately.

---

# Final API Rule

> **Kallula's API must expose durable product truth, not implementation accidents: users manipulate Projects, Runs, commands, interactions, configuration snapshots, evidence, credentials, and Previews; Siesta phases, worker processes, host paths, secret material, and container mechanics remain behind the boundaries already defined by the system.**
