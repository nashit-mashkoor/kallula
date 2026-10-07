# Kallula Documentation

Kallula is a browser-based control plane that uses Siesta as its first software-development engine.

This documentation set is written in **moderately controlled technical English**. It uses about 60% of the ASD-STE100 style: short and direct wording where it improves clarity, while keeping natural engineering language when strict controlled English would make the documents harder to read.

## How to use this documentation

Read the documents in this order when you are new to the project:

```text
Product Requirements
        |
        v
System Architecture
        |
        +-----------------------------+
        |              |              |
        v              v              v
Siesta Adaptation     UX           Security
        \              |              /
         \             |             /
          +------------+------------+
                       |
                       v
          Execution Environment
                       |
                       v
            API & Data Contract
                       |
                       v
            Implementation Plan
```

You do not need to read every document before working on one part of the system. Use the guide below to choose the document that matches your task.

## Documents

### 1. [Product Requirements Document](./Kallula%20%E2%80%94%20Product%20Requirements%20Document.md)

Defines **what Kallula must do** and the product boundaries.

Use it when you need to answer questions such as:

- Is this feature part of Kallula?
- What is required for the first release?
- What behavior does the product promise?
- Which requirements are deferred?

Start here when a product decision is unclear.

### 2. [System Architecture & State Model](./Kallula%20%E2%80%94%20System%20Architecture%20%26%20State%20Model.md)

Defines **how the major parts of Kallula fit together** and which component owns each type of state.

Use it when you work on:

- Projects, Runs, and Execution Attempts;
- lifecycle and state transitions;
- execution leases;
- recovery and reconciliation;
- events and Verified State;
- component boundaries.

Use this document before changing system-wide state or ownership rules.

### 3. [Siesta Engine Adaptation Specification](./Kallula%20%E2%80%94%20Siesta%20Engine%20Adaptation%20Specification.md)

Defines **how Kallula integrates with Siesta without making the rest of Kallula depend on Siesta internals**.

Use it when you work on:

- the Siesta adapter;
- human interaction during Phase 0;
- safe stop and resume;
- stage and Work Item mapping;
- engine events and outcomes;
- Agent Slots;
- Siesta upgrades and compatibility.

Use this document for all code that directly touches Siesta.

### 4. [UX & Interaction Specification](./Kallula%20%E2%80%94%20UX%20%26%20Interaction%20Specification.md)

Defines **what users see and how they control Kallula in the browser**.

Use it when you work on:

- navigation and screens;
- Dashboard behavior;
- Project creation;
- interviews and Pending Interactions;
- Run monitoring;
- stop and resume;
- Files, Git, Preview, Agents, Credentials, and History;
- mobile and accessibility behavior.

Use it as the main guide for frontend behavior.

### 5. [Security & Credentials Design](./Kallula%20%E2%80%94%20Security%20%26%20Credentials%20Design.md)

Defines **the trust model and rules for secrets, credentials, integrations, and untrusted workloads**.

Use it when you work on:

- authentication and sessions;
- credential storage and encryption;
- worker and Pi environments;
- Project runtime secrets;
- GitHub authentication;
- Preview isolation;
- logging and redaction;
- audit and compromise response.

Read this document before adding any new secret or privileged capability.

### 6. [Execution Environment & Preview Design](./Kallula%20%E2%80%94%20Execution%20Environment%20%26%20Preview%20Design.md)

Defines **how Kallula runs autonomous coding work and generated applications**.

Use it when you work on:

- worker containers;
- workspace mounts;
- Run Engine Runtime;
- runtime packs and Environment Snapshots;
- resource and network limits;
- application services;
- Preview build and runtime;
- runtime secret injection;
- Preview routing and health;
- cleanup and crash recovery.

Use it as the main guide for runtime and infrastructure work.

### 7. [API & Data Contract Specification](./Kallula%20%E2%80%94%20API%20%26%20Data%20Contract%20Specification.md)

Defines **the stable data model and contracts between the browser, control plane, runtime, and engine integration**.

Use it when you work on:

- API endpoints;
- database entities;
- commands;
- idempotency;
- optimistic concurrency;
- Event replay and SSE;
- error contracts;
- Preview, Credential, Run, and Interaction schemas.

Use this document when implementation needs an exact field, resource, state, or API contract.


### 8. [Implementation Plan](./Kallula%20%E2%80%94%20Implementation%20Plan.md)

Defines **the order in which Kallula should be built** and the initial technology choices for the first implementation.

Use it when you work on:

- repository and development setup;
- milestone planning;
- implementation dependencies;
- technology selection;
- vertical slices and Definitions of Done;
- deciding what should not be built yet;
- deciding when the project is ready to move to the next milestone.

Use this as the day-to-day implementation guide. When it conflicts with a normative product, architecture, security, runtime, or API rule, the higher-level document wins.

## Local development

The M0 development foundation is tracked in GitHub issues with the `m0` label.

Target local workflow (Implementation Plan §30):

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

Common commands:

```text
make migrate        # apply database migrations
make test           # run backend tests
make lint           # backend lint and format checks
make api            # start the API
make coordinator    # start the coordinator
make web-install    # install frontend dependencies
make web            # start the frontend dev server
make web-test       # run frontend tests
make web-typecheck  # type-check the frontend
make web-build      # build the frontend
make dev            # start the full stack with Docker Compose
```

Run `make help` to see all commands. Docker is required only for `make dev` and the `compose-*` targets.

With the Compose stack running, apply migrations inside the API container:

```text
docker compose run --rm kallula-api alembic upgrade head
```

## Testing

Tests are required, not optional.

```text
make test           # run backend tests
make lint           # backend lint and format checks
make web-test       # run frontend tests
make web-typecheck  # type-check the frontend
```

Rules:

- write tests for every new piece of functionality in the same change;
- keep tests consistent with the code; update affected tests in the same change;
- a piece of functionality is complete only when the full test suite passes;
- never delete or weaken a test only to make it pass.

All automated tests live under the root `tests/` directory.

## Pinned engine

Siesta is vendored under `vendor/siesta` as a Git submodule. The reviewed revision is pinned to:

```text
jairorodriguezarias/siesta @ 20b149e0734b09730dfd22803d2695776fcf84b8
```

Initialize it with:

```text
git submodule update --init --recursive
```

## Current status

M0 (Repository and Development Foundation) is complete. M1 (Project and Run skeleton) is in progress.

```text
M0  Repository and development foundation   [complete]
 |
 v
M1  Project and Run skeleton                [in progress]
 |
 v
M2  Durable Events and live updates
```

Then move to the real Siesta integration in M3–M5.

The **Test & Compatibility Strategy** remains deferred until the implementation is concrete enough to define executable release gates. It becomes required during M12 before release.

## Development and issue tracking

Implementation tasks are tracked as GitHub issues in [`nashit-mashkoor/kallula`](https://github.com/nashit-mashkoor/kallula/issues).

Each milestone uses one issue label. M0 is complete; the current milestone is M1:

```text
label: m0   Repository and Development Foundation   [complete]
label: m1   Project and Run Skeleton                [current]
```

List M1 work:

```text
gh-axi issue list --label m1
```

Or open:

```text
https://github.com/nashit-mashkoor/kallula/issues?q=label%3Am1
```

The issues are ordered by implementation dependency. Create the next milestone label when the current milestone passes its Definition of Done.
