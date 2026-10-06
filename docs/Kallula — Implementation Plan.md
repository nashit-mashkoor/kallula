# Kallula — Implementation Plan

**Document status:** Normative implementation plan — implementation started  
**Product:** Kallula  
**Product requirements:** [`Kallula — Product Requirements Document.md`](./Kallula%20%E2%80%94%20Product%20Requirements%20Document.md)  
**System architecture:** [`Kallula — System Architecture & State Model.md`](./Kallula%20%E2%80%94%20System%20Architecture%20%26%20State%20Model.md)  
**Siesta adaptation:** [`Kallula — Siesta Engine Adaptation Specification.md`](./Kallula%20%E2%80%94%20Siesta%20Engine%20Adaptation%20Specification.md)  
**UX specification:** [`Kallula — UX & Interaction Specification.md`](./Kallula%20%E2%80%94%20UX%20%26%20Interaction%20Specification.md)  
**Security design:** [`Kallula — Security & Credentials Design.md`](./Kallula%20%E2%80%94%20Security%20%26%20Credentials%20Design.md)  
**Execution and Preview design:** [`Kallula — Execution Environment & Preview Design.md`](./Kallula%20%E2%80%94%20Execution%20Environment%20%26%20Preview%20Design.md)  
**API and data contract:** [`Kallula — API & Data Contract Specification.md`](./Kallula%20%E2%80%94%20API%20%26%20Data%20Contract%20Specification.md)  
**Implementation status:** M0 in progress  
**Purpose:** Turn the Kallula design into a sequence of small, working, vertical product slices. Each milestone must produce usable software and preserve the existing architecture.

> **Implementation rule:** Do not build horizontal infrastructure because it might be useful later. Build the smallest complete path that proves the next Kallula capability.

> **Core proof rule:** Milestones M0–M5 must prove that Kallula can own a long-running Siesta Run through the browser, survive disconnects and process restarts, pause for human input, stop safely, resume, and report durable truth. Review the product after M5 before committing to the remaining milestones.

---

# 1. Purpose

The design phase is complete enough to start implementation.

This document defines:

- the initial technology stack;
- the repository structure;
- the implementation boundaries;
- the milestone order;
- dependencies between milestones;
- what each milestone includes;
- what each milestone does not include;
- the minimum validation required at each stage;
- the Definition of Done for each milestone;
- the review gates that decide whether work should continue.

This document does not replace the product, architecture, security, runtime, or API specifications.

If this plan conflicts with those documents, the higher-level specification wins unless the design is formally changed.

---

# 2. Delivery Strategy

Kallula will be built as vertical slices.

Do not build:

```text
all backend
    then
all frontend
    then
all runtime
```

Build:

```text
one complete product behavior
        |
        v
database + API + coordinator + UI
        |
        v
verify that it works
        |
        v
add the next behavior
```

The milestone sequence is:

```text
M0  Repository + development foundation
 |
 v
M1  Project + Run skeleton
 |
 v
M2  Durable Events + live updates
 |
 v
M3  Real Siesta autonomous execution
 |
 v
M4  Durable human interaction
 |
 v
M5  Safe stop + resume + recovery
 |
 +------ CORE PRODUCT REVIEW GATE ------+
 |
 v
M6  Files + Git + verification
 |
 v
M7  Hosted worker isolation
 |
 v
M8  Preview
 |
 v
M9  Agent + Environment configuration
 |
 v
M10 Credentials
 |
 v
M11 GitHub integration
 |
 v
M12 Hardening + release validation
```

---

# 3. Product Review Gates

There are three review gates.

## 3.1 Gate A — after M2

Question:

> Does the Kallula state and event model work without Siesta?

Do not continue to real engine integration if basic Run state, durable commands, event replay, and browser recovery are unreliable.

## 3.2 Gate B — after M5

This is the most important gate.

Question:

> Does Kallula now prove the product thesis?

The system must support this flow:

```text
Create Project
      |
      v
Start Siesta-backed Run
      |
      v
Browser receives durable progress
      |
      +---- browser can disconnect ----+
      |                                |
      v                                |
Siesta asks a question                 |
      |                                |
      v                                |
WAITING_FOR_HUMAN                      |
      |                                |
      v                                |
User answers later <-------------------+
      |
      v
New Execution Attempt
same Run
      |
      v
Safe stop
      |
      v
Resume
      |
      v
Correct durable state after restart
```

If this does not work reliably, do not invest in Preview, credentials, or GitHub.

## 3.3 Gate C — after M8

Question:

> Is Kallula useful as a complete local/self-hosted product before external integrations?

At this point a user should be able to:

- create and run a project;
- interact with Siesta;
- inspect source and verification;
- recover Runs;
- open the generated application in Preview.

Only after this gate should the project add broader configuration and external credential/integration features.

---

# 4. Initial Technology Stack

The first implementation uses a deliberately small stack.

## 4.1 Backend

Use:

- Python 3.12;
- FastAPI;
- Pydantic v2;
- SQLAlchemy 2.x;
- Alembic;
- SQLite through `aiosqlite` for initial development (see §4.3);
- `uv` for Python dependency and environment management;
- `pytest` for backend tests.

Why:

- the API is resource-oriented and async-friendly;
- the existing design already maps well to typed Python models;
- the control-state database can store durable product state, commands, leases, events, and audit data;
- SQLite removes local setup steps while the schema stays portable;
- no Redis/Kafka dependency is needed for the initial single-node architecture.

## 4.2 Frontend

Use:

- React;
- TypeScript;
- Vite;
- React Router;
- TanStack Query;
- native `EventSource` for SSE;
- Radix UI primitives;
- Tailwind CSS for layout and styling;
- Playwright for browser tests later.

Do not build a custom design system before the core interaction model works.

## 4.3 Database

The first implementation uses SQLite through the same SQLAlchemy and Alembic layer.

The database location is one configuration value: `DATABASE_URL`.

SQLite is the development default. PostgreSQL 16+ is restored for hosted or multi-process deployment by changing `DATABASE_URL`. Keep schema definitions and queries dialect-neutral so that the switch is configuration-only.

Do not add:

- Redis;
- Kafka;
- a separate event store;
- Elasticsearch.

The control-state database handles:

- Projects;
- Runs;
- Attempts;
- Commands;
- leases;
- interactions;
- Work Items;
- normalized Events;
- configuration snapshots;
- Preview metadata;
- credentials metadata;
- audit records.

Large files and workspace content remain outside the database.

**Initial database decision (ADR-006):** initial development uses SQLite for zero-setup startup. The target deployment uses PostgreSQL 16+. The switch is a `DATABASE_URL` change followed by a migration run. PostgreSQL-only features are enabled only when the database is PostgreSQL.

## 4.4 Live updates

Use:

```text
durable Event rows in the control-state database
        +
a wake-up signal
        +
SSE to the browser
```

The wake-up signal is not durable truth. It only wakes up the process that delivers data already stored in the database. If notification delivery is missed, the SSE server reads the Event table and replays from the last sequence.

On PostgreSQL, the wake-up signal is `LISTEN/NOTIFY`.

On SQLite, use a polling wake-up interval. The Event table remains the durable contract, so the delivery logic does not change.

## 4.5 Background coordination

Use a separate Python process from the same codebase:

```text
kallula-api
kallula-coordinator
```

The API handles HTTP/SSE.

The coordinator handles:

- accepted Commands;
- Run scheduling;
- Attempt lifecycle;
- reconciliation;
- worker/runtime control.

Both use the same `DATABASE_URL` configuration.

Do not introduce Celery or a distributed queue initially.

## 4.6 Runtime backend

Development:

- Docker Desktop or compatible local Docker Engine.

Initial hosted Linux deployment:

- rootless Docker Engine where practical;
- Runtime Manager uses the Docker Engine API through trusted host access;
- workload containers never receive the Docker socket.

The Runtime Manager interface must keep Docker-specific code in one module.

This allows Podman or another OCI backend later without changing Run semantics.

## 4.7 Preview gateway

Use Caddy for the first implementation.

The Preview Controller owns Caddy route configuration through a private trusted interface.

Preview workloads do not control Caddy.

Do not expose workload container ports directly to the public interface.

## 4.8 Authentication

Build the product around the provider-neutral server session contract from the Security Design.

Initial development mode:

- local development user;
- explicit development-only configuration.

Initial hosted authentication can use an OIDC/OAuth provider through a small backend authentication adapter.

Do not couple Project/Run ownership to a provider-specific user ID.

Provider selection can be made when the first hosted deployment is prepared.

## 4.9 GitHub

Use a GitHub App when M11 begins.

Do not use Personal Access Tokens as the primary hosted integration.

## 4.10 Deployment

Initial local stack:

```text
Docker Compose
|
+-- kallula-api
+-- kallula-coordinator
+-- kallula-web
+-- caddy
```

M0 and M1 use a SQLite file on a shared development volume, so no separate database service is required. Add a `postgres` service when `DATABASE_URL` switches to PostgreSQL.

Execution Worker and Preview containers are created dynamically by the trusted Runtime Manager.

The first release does not need Kubernetes.

---

# 5. Repository Structure

Use one repository.

Recommended structure:

```text
kallula/
|
+-- README.md
+-- pyproject.toml
+-- package.json
+-- docker-compose.yml
+-- .env.example
+-- .gitignore
+-- Makefile
|
+-- docs/
|   |
|   +-- README.md
|   +-- Kallula — Product Requirements Document.md
|   +-- Kallula — System Architecture & State Model.md
|   +-- Kallula — Siesta Engine Adaptation Specification.md
|   +-- Kallula — UX & Interaction Specification.md
|   +-- Kallula — Security & Credentials Design.md
|   +-- Kallula — Execution Environment & Preview Design.md
|   +-- Kallula — API & Data Contract Specification.md
|   +-- Kallula — Implementation Plan.md
|
+-- apps/
|   |
|   +-- api/
|   |   +-- kallula_api/
|   |
|   +-- coordinator/
|   |   +-- kallula_coordinator/
|   |
|   +-- web/
|       +-- src/
|
+-- packages/
|   |
|   +-- domain/
|   +-- persistence/
|   +-- engine/
|   |   +-- base/
|   |   +-- siesta/
|   +-- runtime/
|   |   +-- base/
|   |   +-- docker/
|   +-- integrations/
|   |   +-- github/
|   +-- security/
|   +-- observability/
|
+-- vendor/
|   +-- siesta/
|
+-- migrations/
|
+-- scripts/
|
+-- tests/
    +-- api/
    +-- coordinator/
    +-- web/
    +-- integration/
    +-- fixtures/
```

The exact Python package boundaries can change during M0 if imports become awkward.

The important rules are:

- API routes do not contain engine-specific code;
- Siesta-native code stays in `packages/engine/siesta`;
- runtime backend code stays in `packages/runtime`;
- persistence code does not call Docker or Siesta;
- frontend consumes `/api/v1`, not internal Python models;
- all automated tests live under the root `tests/` directory, never inside `apps/`.

---

# 6. Source of API Types

The API specification remains normative.

During implementation:

```text
Pydantic API models
        |
        v
generated OpenAPI
        |
        v
generated TypeScript client/types
```

The generated frontend types are implementation artifacts.

Do not manually maintain duplicate TypeScript API interfaces when they can be generated.

Generated API code must not contain business decisions.

---

# 7. Database Migration Strategy

Use Alembic from M0.

Rules:

- every schema change uses a migration;
- migrations are committed with the code that needs them;
- no development-only `create_all()` path becomes the production migration system;
- destructive migrations require an explicit data transition;
- event sequence, Run state, configuration snapshots, and Verified State history must never be casually rewritten.

Before the first public release, add backup/restore rehearsal.

---

# 8. Development Configuration

Configuration uses typed application settings.

Categories:

```text
database
session/auth
workspace root
engine installation root
runtime manager
preview gateway
logging
development mode
```

Do not place Project runtime credentials in the general Kallula `.env`.

`.env` can contain development infrastructure configuration only.

Production secrets must use the security design when M10 is implemented.

---

# 9. Logging During Early Development

Before the full redaction system exists:

- do not log request bodies by default;
- never log Authorization or Cookie headers;
- do not print complete process environments;
- keep logs structured;
- include Request ID, Project ID, Run ID, Attempt ID where applicable.

This reduces later cleanup.

---

# 10. Milestone M0 — Repository and Development Foundation

## 10.1 Objective

Create a repository that every later milestone can build on.

No real Kallula product behavior is required yet.

## 10.2 Implement

Backend:

- FastAPI application;
- versioned `/api/v1` router (product endpoints; health stays unversioned);
- health endpoints;
- SQLite connection through `DATABASE_URL`;
- SQLAlchemy base;
- Alembic setup;
- problem/error response helper;
- Request ID middleware;
- development session/principal.

Coordinator:

- separate process entry point;
- database connection;
- startup/shutdown lifecycle;
- no Run execution yet.

Frontend:

- Vite React TypeScript application;
- router;
- API client setup;
- TanStack Query;
- application shell placeholder.

Development:

- Docker Compose;
- SQLite database file;
- API;
- coordinator;
- web;
- Caddy placeholder if convenient;
- format/lint/test commands;
- environment example.

Siesta:

- add the reviewed upstream repository under `vendor/siesta` as a pinned Git submodule or equivalent immutable checkout;
- record the reviewed revision;
- do not modify Siesta yet.

## 10.3 Do not implement

Do not implement:

- Project lifecycle;
- Runs;
- engine execution;
- credentials;
- Preview;
- GitHub;
- worker containers.

## 10.4 Minimum validation

A clean checkout can:

```text
configure DATABASE_URL (SQLite default)
start API
start coordinator
start frontend
open browser
GET /health/ready
```

A migration can be applied to an empty database.

## 10.5 Definition of Done

M0 is done when:

- the repository has the agreed structure;
- one command starts the local development stack;
- frontend can call the backend;
- migrations run from zero;
- automated backend/frontend smoke checks pass;
- Siesta revision is pinned and visible;
- no product behavior has been prematurely built into infrastructure helpers.

---

# 11. Milestone M1 — Project and Run Skeleton

## 11.1 Objective

Prove the Kallula state model before using real Siesta.

Use a fake deterministic engine.

## 11.2 Implement

Database/resources:

- Principal;
- Project;
- Workspace metadata;
- Run;
- Run Config Snapshot;
- Execution Attempt;
- Project execution lease;
- Command;
- idempotency record.

API:

- `GET /session`;
- Project create/list/get/update;
- Run create/get/list;
- Run configuration read;
- Command read.

Coordinator:

- claim accepted Run;
- acquire Project lease;
- create Execution Attempt;
- fake engine transitions;
- release lease.

Fake engine behavior:

```text
QUEUED
  |
  v
STARTING
  |
  v
RUNNING
  |
  v
COMPLETED
```

Frontend:

- Dashboard;
- Projects list;
- Create Project;
- Project shell;
- basic Current Run page.

## 11.3 State correctness

The database must be the source of truth.

Do not let frontend state decide Run state.

A coordinator restart must not delete or recreate a Run.

## 11.4 Do not implement

Do not add:

- real Siesta;
- SSE;
- human interaction;
- Preview;
- credentials;
- GitHub.

Polling is acceptable for the temporary M1 UI.

## 11.5 Minimum validation

Test:

- Project creation is idempotent;
- Run creation is idempotent;
- one Project cannot get two valid execution leases;
- Run state survives API restart;
- terminal `COMPLETED` does not return to running states;
- stale Project PATCH fails with ETag mismatch.

## 11.6 Definition of Done

M1 is done when a user can create a Project and see a fake Run complete through the browser.

Restarting the API during the Run must not erase Project or Run state.

---

# 12. Milestone M2 — Durable Events and Live Updates

## 12.1 Objective

Prove durable observability and reconnect behavior.

## 12.2 Implement

Database:

- Event table;
- Run-local sequence allocation;
- event payload version;
- normalized Event categories.

API:

- Event list;
- `after_sequence`;
- Run SSE endpoint;
- account/project invalidation SSE stream.

Coordinator/fake engine:

- create structured Events for every Run transition;
- append Event and update Run projection in one transaction where required;
- use the wake-up signal only after commit (PostgreSQL `NOTIFY`, or the SQLite polling fallback from §4.4).

Frontend:

- Activity page;
- live Run state;
- reconnect;
- event replay;
- freshness indicator.

## 12.3 Required invariant

The system must work when every `NOTIFY` is lost.

The Event table is durable.

Notification is only a wake-up signal.

## 12.4 Do not implement

Do not add:

- Redis pub/sub;
- WebSockets;
- Kafka;
- real Siesta.

## 12.5 Minimum validation

Test:

```text
start Run
receive events
disconnect browser
allow Run to continue
reconnect with Last-Event-ID
receive missed events
continue live
```

Also test duplicate SSE delivery.

## 12.6 Definition of Done

M2 is done when the browser can reconstruct a Run after disconnect without guessing what happened.

---

# 13. Gate A Review

Before M3, confirm:

- Run state machine is stable;
- Event sequence is stable;
- commands are idempotent;
- SSE reconnect works;
- API restart does not corrupt active Runs;
- the frontend does not depend on fake-engine internals.

If any of these fail, fix them before integrating Siesta.

---

# 14. Milestone M3 — Real Siesta Autonomous Execution

## 14.1 Objective

Run the real pinned Siesta engine through Kallula for the first time.

Use autonomous/default mode first.

Do not solve browser interview behavior in the same milestone.

## 14.2 Siesta adaptation work

Implement the minimum adapter seam required by the Siesta Adaptation Specification:

- programmatic launch entry point;
- exact external workspace injection;
- structured Event hook;
- structured terminal outcome;
- narrow child environment;
- engine identity/capability inspection;
- artifact discovery;
- native-state inspection.

Phase 0 may use auto/default behavior in this milestone.

## 14.3 Engine Installation

Implement:

- Engine Installation record;
- pinned Siesta revision;
- adapter version;
- installation digest/identity;
- capability manifest;
- compatibility status for launch.

The installed engine is read-only from the Run.

## 14.4 Workspace

Implement physical canonical Project workspace.

For a new Project:

```text
Project created
      |
      v
workspace allocated
      |
      v
Git repository initialized
      |
      v
Run executes against this workspace
```

The workspace survives Attempt exit.

## 14.5 Run Engine Runtime

Implement the first durable Run-scoped engine runtime.

It must survive Attempt destruction.

It must remain separate from Project source.

## 14.6 Normalization

Map current Siesta into:

- Stage;
- Work Item;
- Artifact;
- test evidence;
- verification evidence;
- semantic terminal outcome.

Do not expose `phase-3`, checkpoint file paths, or native filenames as required frontend fields.

## 14.7 Frontend

Add:

- Stage display;
- Work Item summary;
- Activity based on real adapter Events;
- basic Artifact links;
- engine identity in Run configuration.

## 14.8 Do not implement

Do not add:

- durable human interview;
- safe stop;
- resume;
- worker container isolation;
- Preview.

The engine may still run as a development process at this milestone.

This is allowed only in explicit development mode.

## 14.9 Minimum validation

Run at least:

- one very small generated project;
- one Run that completes;
- one Run that fails;
- one Run that creates multiple Work Items.

Confirm that Kallula state comes from normalized adapter output, not console text parsing.

## 14.10 Definition of Done

M3 is done when a user can create a Project in Kallula and a real Siesta Run can plan, build, review, verify, and finish while the browser shows normalized durable progress.

---

# 15. Milestone M4 — Durable Human Interaction

## 15.1 Objective

Move Siesta Phase 0 from terminal input to Kallula's durable interaction model.

## 15.2 Implement

Siesta adaptation:

- external human-interaction hook;
- durable native interaction identity;
- persisted Phase 0 state;
- exact current question;
- recommendation/default;
- final intent confirmation;
- answer consumption exactly once.

Kallula persistence:

- Pending Interaction;
- Interaction Response;
- interaction Command;
- at most one open interaction per Run.

Run lifecycle:

```text
RUNNING
   |
   v
engine opens interaction
   |
   v
WAITING_FOR_HUMAN
   |
   v
Attempt exits
   |
   +----- time passes -----+
   |
user answers
   |
   v
Run -> QUEUED
   |
   v
new Attempt
   |
   v
same Run continues
```

## 15.3 Frontend

Implement the interview UI from the UX specification:

- exact question;
- answer input;
- use recommendation;
- delegate remaining questions where supported;
- final intent confirmation;
- request change;
- reconnect restores open interaction.

## 15.4 Important behavior

The worker must not stay alive waiting for browser input.

Closing the browser must not lose the question.

Submitting the same answer twice must not feed the engine twice.

## 15.5 Do not implement

Do not add:

- free-form agent chat;
- arbitrary steering;
- manual source editing.

## 15.6 Minimum validation

Test:

- browser closes while question is open;
- API restarts while question is open;
- answer is submitted from a new browser session;
- duplicate answer retry;
- two different answers race;
- final intent confirmation;
- delegate/default flow.

## 15.7 Definition of Done

M4 is done when Siesta can ask a requirements question, release the worker, and continue the same Run later after a browser answer.

---

# 16. Milestone M5 — Safe Stop, Resume, and Recovery

## 16.1 Objective

Prove that Kallula owns Run lifecycle independently from one process.

## 16.2 Implement safe stop

API:

```text
POST /runs/{id}/commands/stop
```

Lifecycle:

```text
RUNNING
   |
   v
STOP_REQUESTED
   |
   v
adapter requests native safe stop
   |
   v
engine reaches safe boundary
   |
   v
Attempt exits
   |
   v
STOPPED
```

Do not report `STOPPED` at command acceptance.

## 16.3 Implement resume

Resume must:

- keep the same Run ID;
- create a new Attempt;
- reuse canonical Workspace;
- reuse Run Engine Runtime;
- use pinned Engine Installation;
- use pinned Environment Snapshot when that feature exists;
- fail closed on incompatible native state.

## 16.4 Implement reconciliation

On coordinator startup:

- inspect active Runs;
- inspect leases;
- inspect known process/runtime state;
- inspect engine-native workspace state;
- decide the correct normalized state.

Initial development-process execution may use PID/process records.

Later M7 replaces this with Runtime Manager/container inspection.

## 16.5 Implement lease epochs

Use a lease epoch/fencing value so stale Attempt ownership cannot renew a newer lease.

## 16.6 Failure cases

Handle:

- API restart;
- coordinator restart;
- worker/engine process exits unexpectedly;
- stop requested while engine completes;
- process exit code 0 without semantic completion;
- native stop marker exists;
- pending interaction exists;
- resume compatibility fails.

## 16.7 Frontend

Implement:

- Stop safely;
- `STOP_REQUESTED` presentation;
- Resume;
- blocked resume explanation;
- Attempt history;
- failure/recovery evidence.

## 16.8 Minimum validation

Run scripted fault cases.

Do not depend only on normal-path manual testing.

## 16.9 Definition of Done

M5 is done when a real Siesta Run can:

- pause for human input;
- survive browser disconnect;
- stop safely;
- resume as the same Run;
- create a new Attempt;
- survive API/coordinator restart;
- never claim success from process exit alone.

---

# 17. Gate B — Core Product Proof

Stop feature work after M5.

Run an explicit review.

The review must answer:

## Product

- Is browser-controlled Siesta execution actually useful?
- Does the Project/Run model feel natural?
- Does WAITING_FOR_HUMAN work well?
- Does safe stop/resume solve a real problem?

## Architecture

- Are Run and Attempt boundaries still correct?
- Is the adapter boundary holding?
- Are native Siesta details leaking into UI/API code?
- Is reconciliation understandable?

## Reliability

- Can a developer explain every active Run after a restart?
- Can the system recover without manually editing database rows?
- Are there ambiguous states that the current model does not express?

## Decision

Choose one:

```text
CONTINUE
```

The thesis is working. Continue to M6.

```text
REVISE
```

Keep the product but change part of the state/adapter model before adding features.

```text
STOP
```

The central product assumption is not useful enough to justify more infrastructure.

No M6+ work should begin before this review.

---

# 18. Milestone M6 — Files, Git, and Verification

## 18.1 Objective

Make Kallula useful for inspecting the software that Siesta created.

## 18.2 Implement Files

Read-only v1:

- directory listing;
- text file view;
- raw file download;
- source selector;
- path containment;
- symlink safety.

Do not add browser editing.

## 18.3 Implement Git

Expose:

- current branch;
- HEAD;
- dirty status;
- commit list;
- commit detail;
- diff;
- Verified State commit.

## 18.4 Initial branch policy

For new Projects:

- initialize local Git repository;
- maintain a stable Project base branch;
- each new Run works on `kallula/run-<ordinal>`;
- a new Run starts from the current accepted Project HEAD;
- Kallula never needs to rewrite remote default branches.

For imported repositories:

- start from the user-selected base ref;
- work on a Kallula-managed Run branch;
- do not push until M11.

The exact user-facing branch labels may be adjusted, but the invariant is that Kallula does not silently commit directly to a remote protected/default branch.

## 18.5 Implement verification

Persist:

- Verification Result;
- evidence Artifact references;
- exact verified commit;
- Verified State.

Frontend must clearly show:

```text
Current source
!=
Last Verified State
```

when they differ.

## 18.6 Implement export

Add source ZIP export from a stable source identity.

Do not include:

- platform secrets;
- Run Engine Runtime;
- runtime state;
- host files.

## 18.7 Definition of Done

M6 is done when a user can inspect source, Git history, test/verification evidence, current state, and last Verified State without server access.

---

# 19. Milestone M7 — Hosted Worker Isolation

## 19.1 Objective

Replace development-process execution with the production execution boundary.

## 19.2 Implement Runtime Manager

Create the trusted Docker-backed driver.

It supports:

- create worker;
- inspect worker;
- stop worker;
- delete worker;
- logs;
- resource limits;
- network creation;
- mount validation.

## 19.3 Worker composition

Attach:

```text
Engine Installation       read-only
Canonical Workspace       read-write
Run Engine Runtime        read-write
Scratch/tmp/cache         disposable
```

Do not attach:

```text
Docker socket
control DB credentials
GitHub credentials
credential store
host home
other Projects
```

## 19.4 Harden worker

Use:

- non-root user;
- no privileged mode;
- no host network;
- dropped capabilities;
- no-new-privileges;
- CPU limit;
- memory limit;
- PID limit;
- timeout;
- bounded scratch storage.

## 19.5 Network

Worker can use required public internet access.

Block:

- control database;
- internal credential boundary;
- host/container runtime administration;
- metadata endpoints;
- other Project networks.

## 19.6 Reconciliation

Update M5 reconciliation to inspect runtime/container identity instead of relying on local process state.

## 19.7 Definition of Done

M7 is done when the M5 product flow works entirely through disposable isolated workers and the Project can resume after worker deletion.

---

# 20. Milestone M8 — Preview

## 20.1 Objective

Run and inspect the generated application without mixing application runtime with the coding worker.

## 20.2 Start small

The first Preview supports:

- one primary application service;
- one committed source snapshot;
- one Runtime Plan;
- HTTP health check;
- runtime logs;
- one Preview Gateway route.

Do not begin with arbitrary Compose.

## 20.3 Runtime Plan

Implement conservative auto-detection for a small supported set.

Initial candidates:

- Python web service;
- Node web service;
- Python backend + Node frontend only after single-service paths work.

If detection is uncertain:

```text
NOT_RUNNABLE
```

with an explanation.

Do not guess repeatedly.

## 20.4 Source snapshot

Preview uses a committed source state.

It never mounts the writable canonical Workspace.

If the workspace is dirty:

- Preview the latest committed state;
- show that newer uncommitted changes exist.

## 20.5 Build/runtime separation

Preview build:

- no Project runtime credentials;
- bounded network/resources.

Application runtime:

- separate container;
- no coding agent;
- no control-plane authority.

## 20.6 Gateway

Use Caddy.

Hosted production design:

```text
control.example.com
preview-id.preview.example.net
```

Use a separate registrable Preview domain in production.

Development can use localhost routes.

## 20.7 Definition of Done

M8 is done when a user can open a stable, isolated Preview of an exact commit and see runtime health/logs without knowing host ports.

---

# 21. Gate C — Useful Self-Hosted Product

After M8, evaluate the product as if credentials and GitHub did not exist.

A developer should be able to:

- create a Project;
- run Siesta;
- answer questions;
- stop/resume;
- inspect source and Git;
- understand verification;
- open Preview;
- export source.

If this workflow is weak, fix it before expanding settings/integrations.

---

# 22. Milestone M9 — Agent and Environment Configuration

## 22.1 Objective

Expose controlled configuration without exposing protected engine protocol.

## 22.2 Agent Profiles

Implement:

- Agent Profile;
- immutable Agent Profile Version;
- Planner;
- Worker;
- Consultant;
- provider;
- model;
- supported reasoning/settings;
- capability validation.

Do not invent separate Reviewer/Learner slots when current Siesta does not expose them as independent configuration slots.

## 22.3 Environment Profiles

Implement:

- Auto;
- explicit runtime pack selection;
- resource class;
- network mode;
- supported service capability choices.

## 22.4 Environment Snapshot

Freeze the resolved environment on Run creation.

Existing Runs do not change when defaults change.

## 22.5 Configuration UI

Add:

- global Agent Profiles;
- Project default Agent Profile;
- Environment Profile;
- Run configuration read-only snapshot;
- capability-driven controls.

## 22.6 Definition of Done

M9 is done when a user can change a supported model/environment for future Runs and historical Runs still show exactly what they used.

---

# 23. Milestone M10 — Credentials and Runtime Secret Injection

## 23.1 Objective

Add real secrets only after Run and Preview boundaries are stable.

## 23.2 Key provider

Implement a KeyProvider interface.

Development:

- local development key;
- clearly marked insecure/non-production mode.

Hosted:

- use a protected deployment key or external KMS-backed provider.

The interface must support future KEK rotation.

## 23.3 Credential storage

Implement:

- Credential metadata;
- Credential Value Versions;
- envelope encryption;
- create;
- replace;
- revoke/delete;
- Project assignment;
- no reveal.

## 23.4 Redaction

Add:

- known-secret redaction registry;
- request/log safeguards;
- runtime log redaction;
- diagnostic redaction.

## 23.5 Runtime injection

Only Preview application services receive assigned Project runtime credentials.

Worker and Preview build do not receive them.

## 23.6 Audit

Record:

- credential create;
- replace;
- assign;
- unassign;
- revoke/delete;
- runtime grant;
- denied access.

Never store the value in audit.

## 23.7 Definition of Done

M10 is done when an application can use an assigned secret at runtime while that value remains absent from:

- source;
- Git;
- coding worker environment;
- build environment;
- API read responses;
- logs;
- audit events.

---

# 24. Milestone M11 — GitHub Integration

## 24.1 Objective

Add trusted remote repository import and publishing.

## 24.2 GitHub App

Implement:

- App installation flow;
- installation metadata;
- repository discovery;
- short-lived installation token minting;
- disconnect/revoke behavior.

The token stays in the trusted Integration layer.

## 24.3 Import

Trusted integration clones/fetches the selected repository.

The workspace must not keep credentials in the remote URL.

After import, local Git operations require no GitHub token.

## 24.4 Publish

Implement:

- push Kallula Run branch;
- open Pull Request;
- publish operation resource;
- durable external-operation result.

Do not let Siesta/Pi call GitHub directly.

## 24.5 Definition of Done

M11 is done when Kallula can import a private authorized repository, run locally, and publish a branch/PR without exposing GitHub credentials to the coding worker.

---

# 25. Milestone M12 — Hardening and Release Validation

## 25.1 Objective

Turn the working product into a release candidate.

This is the point where the deferred **Test & Compatibility Strategy** should be written as a separate document.

The strategy must reflect the real implementation rather than imagined infrastructure.

## 25.2 Required hardening areas

Formalize and automate:

- state-machine tests;
- lease race tests;
- idempotency tests;
- database migration tests;
- SSE reconnect/replay tests;
- fake adapter tests;
- real Siesta compatibility tests;
- safe stop/resume tests;
- crash/reconciliation tests;
- worker mount/network isolation tests;
- credential leak canary tests;
- Preview isolation tests;
- GitHub integration tests;
- browser E2E tests;
- backup/restore rehearsal.

## 25.3 Engine upgrade gate

For every new Siesta revision:

```text
candidate Engine Installation
          |
          v
compatibility suite
          |
    +-----+------+
    |            |
    v            v
 supported     rejected
    |
    v
new Runs may use it
```

Existing Runs stay pinned unless migration is explicitly supported.

## 25.4 Operational hardening

Add:

- production session store/config;
- HTTPS;
- secure headers;
- backup policy;
- database recovery procedure;
- key backup/recovery;
- log retention;
- storage quota policy;
- runtime cleanup jobs;
- engine/runtime installation cleanup;
- deployment health checks.

## 25.5 Definition of Done

M12 is done when a fresh production-like environment can be deployed, restored from backup, upgraded through a tested migration, and run through the complete browser workflow without privileged manual repair.

---

# 26. Implementation Priorities

When trade-offs appear, use this order:

1. state correctness;
2. resumability/recovery;
3. security boundaries;
4. engine isolation;
5. user clarity;
6. observability;
7. performance;
8. convenience;
9. visual polish.

Do not sacrifice durable correctness for a faster-looking UI.

---

# 27. What Must Not Be Built Early

Do not add these before a concrete requirement appears:

- Kubernetes;
- Kafka;
- Redis as mandatory infrastructure;
- microservices for each logical component;
- service mesh;
- generic engine plugin marketplace;
- multi-region execution;
- multiple simultaneous autonomous writers per Project;
- production application hosting;
- arbitrary Docker Compose execution;
- browser terminal;
- browser source editing;
- collaborative coding;
- agent marketplace;
- billing;
- enterprise RBAC;
- generic workflow builder.

These features can be designed later if the product proves that it needs them.

---

# 28. Minimum Testing During Implementation

The full Test & Compatibility Strategy is deferred, but implementation is never test-free.

Testing rules are mandatory:

- every new piece of functionality includes tests in the same change;
- tests stay consistent with the code they cover;
- a capability is complete only when the full test suite passes;
- a failing test is never weakened or deleted only to make it pass.

Each milestone must include tests for the behavior it introduces.

Minimum layers:

```text
unit tests
    |
    v
database/domain tests
    |
    v
API tests
    |
    v
integration test for the milestone flow
```

From M3 onward, also include a small number of real-engine smoke tests.

From M7 onward, include real runtime isolation tests.

From M8 onward, include browser Preview tests.

The deferred test strategy formalizes and expands these checks before release.

---

# 29. Fake Engine Strategy

M1 and M2 require a deterministic fake engine.

It should be intentionally small.

Example scenarios:

```text
complete_immediately
fail_during_execution
emit_work_items
wait_for_human
stop_at_safe_boundary
crash_without_outcome
```

The fake engine uses the same stable Kallula engine interface as the Siesta adapter.

Do not make it simulate Siesta internals.

Its purpose is to test Kallula.

---

# 30. Local Developer Workflow

The target local workflow is:

```text
git clone
   |
   v
initialize submodules/dependencies
   |
   v
copy .env.example
   |
   v
uv sync
pnpm install
   |
   v
run migrations
   |
   v
start API + coordinator + web
```

SQLite needs no separate database service. Set `DATABASE_URL` to PostgreSQL when a database service is required.

Add one convenience command after the basic pieces work.

Example:

```text
make dev
```

Do not hide important setup behind a complex bootstrap script too early.

---

# 31. CI Sequence

Initial CI should stay small.

M0:

- Python formatting/lint;
- Python unit tests;
- frontend type check;
- frontend build;
- migration check.

M1–M2:

- database integration tests;
- API tests;
- state/event tests.

M3+:

- fake engine integration;
- selected Siesta smoke job.

M7+:

- Linux runtime isolation job.

M8+:

- Preview browser test.

M10+:

- secret leak canary tests.

M11+:

- GitHub integration tests against a controlled test installation/repository where practical.

Do not require every expensive real-model test on every commit.

---

# 32. Technology Decision Log

The following first-release choices are made by this plan.

| Area | Initial choice | Reason |
|---|---|---|
| Backend | FastAPI / Python 3.12 | Fits domain and engine integration |
| Validation | Pydantic v2 | Typed API/config models |
| ORM | SQLAlchemy 2.x | Explicit relational control |
| Database (development) | SQLite via `aiosqlite` | Zero-setup local development |
| Database (target) | PostgreSQL 16+ | Durable state, leases, events, `LISTEN/NOTIFY` |
| Migrations | Alembic | Explicit schema history |
| Python env | `uv` | Fast reproducible tooling |
| Frontend | React + TypeScript + Vite | Mature browser application stack |
| Data fetching | TanStack Query | Server-state management |
| Live events | SSE / EventSource | Matches one-way durable Run updates |
| Wake-up signal | PostgreSQL `LISTEN/NOTIFY`; SQLite polling fallback | Avoids Redis initially |
| Runtime | Docker-compatible OCI backend | Practical first isolated runtime |
| Hosted runtime mode | Rootless Docker where practical | Lower host privilege |
| Local orchestration | Docker Compose | Simple single-node development |
| Preview gateway | Caddy | Small trusted reverse-proxy boundary |
| GitHub auth | GitHub App | Narrow, short-lived repository authority |
| API type sharing | OpenAPI generation | Avoid duplicate contract definitions |
| Browser E2E | Playwright | Cross-browser workflow validation |

A later implementation decision can replace one of these choices only if:

- the replacement preserves the normative contracts;
- the reason is documented;
- migration cost is understood.

---

# 33. First Implementation Target

Do not begin by trying to complete the whole plan.

Implementation tasks are tracked as GitHub issues in the project repository. Each milestone uses one issue label (`m0`, `m1`, ...). List the current milestone with `gh-axi issue list --label m0` or the equivalent GitHub filter.

The first active development target is:

```text
M0
+
M1
+
M2
```

This produces a complete Kallula control-plane skeleton with no Siesta risk.

Then complete:

```text
M3
+
M4
+
M5
```

This proves the real product thesis.

Only after Gate B should the team commit to M6–M12.

---

# 34. Recommended First Issues

Create the first implementation issues in this order:

1. repository/bootstrap;
2. SQLite + Alembic baseline (PostgreSQL later);
3. Principal + development session;
4. Project schema/API;
5. Run schema/API;
6. Command + idempotency records;
7. Project execution lease;
8. Execution Attempt lifecycle;
9. deterministic fake engine;
10. coordinator command loop;
11. Project/Run frontend;
12. Event journal;
13. Event sequence allocator;
14. Run Event SSE;
15. frontend replay/reconnect;
16. account invalidation stream;
17. Gate A integration scenario;
18. Engine interface package;
19. Siesta installation metadata;
20. external Workspace Manager.

Do not create hundreds of detailed tickets before M0 is complete.

Refine the next milestone as the current milestone approaches completion.

---

# 35. Definition of a Complete Vertical Slice

A capability is not done because backend code exists.

A Kallula vertical slice is complete only when all required layers are present:

```text
database / durable state
        |
        v
domain rules
        |
        v
API / command
        |
        v
coordinator or integration behavior
        |
        v
normalized Event / evidence
        |
        v
browser UX
        |
        v
reconnect / failure behavior
        |
        v
tests for the slice
```

If a layer is intentionally not needed, the milestone must state why.

---

# 36. Documentation During Implementation

Do not rewrite the architecture for every code change.

Update normative documents only when implementation discovers a real conflict or missing rule.

Use:

- code comments for local implementation details;
- ADRs for important technology/implementation decisions;
- migrations for schema history;
- the normative Kallula documents for product/system contracts.

Recommended ADR examples:

```text
ADR-001 PostgreSQL transaction isolation choice
ADR-002 Runtime Manager Docker driver
ADR-003 Preview gateway route update mechanism
ADR-004 Hosted authentication provider
ADR-005 Workspace backup mechanism
ADR-006 Initial SQLite development database and PostgreSQL switch
```

Do not use ADRs to override product requirements silently.

---

# 37. Handling Design Gaps

When implementation finds a question that the documents do not answer:

1. stop only the affected feature;
2. identify which normative document owns the question;
3. make the smallest decision needed;
4. update that document or add an ADR if it is implementation-specific;
5. continue.

Do not solve an unclear architecture question with hidden behavior in code.

---

# 38. Implementation Success Criteria

The implementation phase is successful when Kallula can demonstrate this complete path:

```text
User signs in
    |
    v
creates/imports Project
    |
    v
starts Run
    |
    v
Siesta asks questions through browser
    |
    v
Run continues across Attempts
    |
    v
browser can disconnect/reconnect
    |
    v
user can stop safely and resume
    |
    v
Kallula shows Work Items, Events, source, Git, tests
    |
    v
Verified State is clear
    |
    v
user opens isolated Preview
    |
    v
optional runtime secrets are injected safely
    |
    v
source can be exported or published through GitHub
```

At no point should the user need shell access to the server to understand or operate a normal Project.

---

# 39. Final Implementation Rule

> **Build Kallula by proving one durable product behavior at a time. First prove that Kallula can own a Siesta Run correctly. Then add source inspection, isolation, Preview, configuration, credentials, and integrations around that proven core.**
