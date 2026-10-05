# Kallula — System Architecture & State Model

**Document status:** Normative architecture specification — pre-implementation
**Product:** Kallula
**Primary product specification:** [`Kallula — Product Requirements Document.md`](./Kallula%20%E2%80%94%20Product%20Requirements%20Document.md)
**Normative Siesta integration specification:** [`Kallula — Siesta Engine Adaptation Specification.md`](./Kallula%20%E2%80%94%20Siesta%20Engine%20Adaptation%20Specification.md)
**Normative UX & interaction specification:** [`Kallula — UX & Interaction Specification.md`](./Kallula%20%E2%80%94%20UX%20%26%20Interaction%20Specification.md)
**Normative security & credentials design:** [`Kallula — Security & Credentials Design.md`](./Kallula%20%E2%80%94%20Security%20%26%20Credentials%20Design.md)
**Normative execution environment & Preview design:** [`Kallula — Execution Environment & Preview Design.md`](./Kallula%20%E2%80%94%20Execution%20Environment%20%26%20Preview%20Design.md)
**Normative API & data contract specification:** [`Kallula — API & Data Contract Specification.md`](./Kallula%20%E2%80%94%20API%20%26%20Data%20Contract%20Specification.md)
**Initial execution engine:** Siesta (`jairorodriguezarias/siesta`)
**Siesta repository baseline reviewed:** `main`, tree/commit snapshot `20b149e0734b09730dfd22803d2695776fcf84b8`
**Implementation plan:** [`Kallula — Implementation Plan.md`](./Kallula%20%E2%80%94%20Implementation%20Plan.md)  
**Implementation status:** Not started
**Purpose:** Define Kallula's system boundaries, ownership model, state machines, persistence semantics, execution lifecycle, concurrency rules, recovery behavior, and engine-isolation architecture before API or infrastructure implementation decisions are made.
**Audience:** Backend/control-plane, engine-integration, frontend, infrastructure, security, QA, and future maintainers.

> **Normative relationship:** The PRD defines **what Kallula must do** and the product invariants it must preserve. This document defines the **architectural model by which those requirements are represented and coordinated**. The linked **Siesta Engine Adaptation Specification** defines how the current Siesta baseline implements engine-facing portions of this model. The linked **UX & Interaction Specification** defines how the architecture's states, capabilities, truth boundaries, and recovery semantics are presented and manipulated through the browser. The linked **Security & Credentials Design** defines the deployable trust, authentication, secret, integration, Preview-security, redaction, and audit policies that constrain the runtime. The linked **Execution Environment & Preview Design** defines the physical worker, workspace, Run Engine Runtime, Environment Snapshot, network, generated-application, Preview routing, and runtime recovery model. The linked **API & Data Contract Specification** encodes those concepts as stable logical records, browser-facing HTTP resources, durable commands, normalized Events, concurrency/idempotency contracts, and SSE replay/live delivery. Precedence is **PRD → System Architecture & State Model → supporting engine/UX/security/runtime/API specifications within their scopes**; conflicts must be reconciled deliberately.

> **Implementation rule:** A logical component described here is not automatically a separately deployed service. Components may initially live in the same application or host when that is the simplest correct implementation. The boundaries in this document are boundaries of responsibility and state ownership, not a mandate for microservices.

---

# 1. Purpose

The Kallula PRD intentionally leaves a number of architectural mechanisms unresolved. That is appropriate at the product-requirements stage, but implementation cannot begin safely until the system has a coherent answer to questions such as:

- What does Kallula own and what does Siesta own?
- What is authoritative when the control-plane database and project filesystem disagree?
- What is a Project, Run, and resumed execution at the system level?
- What survives a browser disconnect, web-process restart, worker crash, or host restart?
- How does only one autonomous writer modify a project workspace at a time?
- How are long-running executions coordinated without tying them to a web request?
- How does Kallula know whether a run is running, waiting, stopped, failed, or completed?
- What does “last verified state” mean mechanically?
- How are engine-specific checkpoints, stages, roles, and files prevented from spreading throughout Kallula?
- How can a later Siesta revision be adopted without forcing coordinated rewrites of the UI, persistence model, and product APIs?

This document resolves those questions at the architectural level.

It does **not** define final database tables, REST paths, Python class names, queue technology, container runtime, secret-management product, reverse proxy, or frontend framework.

---

# 2. Scope

This document is authoritative for:

1. logical system components and their responsibilities;
2. product-state ownership and sources of truth;
3. Project, Run, Execution Attempt, Interaction, Preview, and Verified State lifecycles;
4. control-state transition rules;
5. execution ownership and single-writer semantics;
6. command durability and idempotency requirements;
7. normalized event durability and ordering requirements;
8. workspace and Git ownership;
9. crash detection, reconciliation, and recovery principles;
10. start, wait-for-human, stop, resume, completion, and failure flows;
11. engine version pinning and architectural upgrade behavior;
12. logical trust boundaries relevant to architecture;
13. initial deployment constraints and permitted simplifications;
14. boundaries delegated to later supporting specifications.

This document is not authoritative for:

- exact Siesta source-code changes;
- exact engine-adapter method signatures;
- exact database schema;
- exact public API contracts;
- exact UI layouts;
- detailed threat modeling or cryptographic key management;
- exact worker sandbox technology;
- exact preview routing/proxy implementation;
- GitHub authentication details;
- billing, enterprise tenancy, or distributed-scale architecture.

Those belong to the supporting specifications identified later in this document and in the PRD.

---

# 3. Architectural Drivers From the PRD

The architecture is driven primarily by the following product invariants.

## 3.1 Browser independence

A browser is a control and observation client, not an execution host.

Closing a tab, refreshing the application, losing a websocket/SSE connection, changing devices, or restarting the frontend must not terminate autonomous execution or lose a pending human interaction.

## 3.2 Durable canonical workspace

Each Project has one canonical durable workspace containing the actual source tree, Git repository, and engine-native project state.

Workers may be disposable. The workspace may not be.

## 3.3 Kallula state and engine state are related but distinct

Kallula owns durable product/control state.

Siesta owns its execution semantics and native checkpoint/project artifacts.

Neither may be casually substituted for the other.

## 3.4 Mechanical evidence is authoritative for verification

Kallula must not translate model narration into test or verification success when mechanical evidence disagrees.

## 3.5 Current state is not verified state

The live workspace may contain changes newer than the most recently verified checkpoint.

The product must preserve this distinction structurally, not merely through UI copy.

## 3.6 Execution must be recoverable when safe

Process loss is not equivalent to project loss.

Kallula must preserve enough control state, workspace state, engine checkpoint state, and execution evidence to decide whether a run can safely continue.

## 3.7 Engine evolution must be contained

The rest of Kallula must not directly depend on current Siesta phase numbers, role names, native filenames, `input()`, `stop.md`, or checkpoint file format.

The Siesta adapter is the architectural anti-corruption layer between Kallula product concepts and engine-native behavior.

## 3.8 Single-writer safety before parallelism

Current Siesta is designed around a single execution process modifying a project/KB at a time.

Kallula must preserve that property until a future engine version and explicit product design safely support greater concurrency.

## 3.9 No speculative distributed architecture

The first implementation should run on a modest single deployment while preserving durable state and process isolation.

Scale-out mechanisms should be introduced only when actual product requirements demand them.

---

# 4. Architectural Principles

The following principles are normative.

**KAL-ARCH-001 — Product state ownership** Kallula owns product/control state; the engine owns engine-native execution state.

**KAL-ARCH-002 — One canonical workspace** There must be one authoritative writable project workspace for a Project at a time.

**KAL-ARCH-003 — One active autonomous writer** At most one autonomous execution attempt may hold the write lease for a Project workspace at a time in the initial architecture.

**KAL-ARCH-004 — Durable intent before execution** A user action that changes execution state must be durably accepted before an asynchronous worker is expected to perform it.

**KAL-ARCH-005 — No web-request ownership of long work** Long-running engine execution must never rely on a web request remaining open.

**KAL-ARCH-006 — Adapter isolation** Only the engine adapter/integration layer may interpret engine-native phases, checkpoints, artifact names, role names, or stop semantics.

**KAL-ARCH-007 — Immutable run configuration** Once a Run begins, the effective execution configuration for that Run is immutable. Later default/profile changes affect later Runs, not the active Run.

**KAL-ARCH-008 — Attempt separation** Worker/process lifetimes are Execution Attempts underneath a Run. A process restart does not automatically imply a new logical Run.

**KAL-ARCH-009 — Explicit reconciliation** After uncertain process failure, Kallula must reconcile control state against workspace/engine evidence. It must not infer completion from absence of a running process.

**KAL-ARCH-010 — Append-first observability** Significant state transitions must leave durable event evidence before or atomically with externally visible product-state changes where practical.

**KAL-ARCH-011 — Truthful terminal state** A Run reaches `COMPLETED` only after the adapter has translated the engine result and Kallula has persisted a coherent terminal result. Process exit alone is insufficient.

**KAL-ARCH-012 — Fail closed on incompatible resume** If stored checkpoint state cannot be shown compatible with the pinned engine/adapter, automatic resume must not occur.

**KAL-ARCH-013 — Capability-driven behavior** UI and control-plane behavior must be based on normalized capabilities reported for the pinned engine/adapter rather than assumptions about all Siesta versions.

**KAL-ARCH-014 — Simple initial topology** Logical boundaries must not be confused with deployment boundaries. The first implementation may co-locate components when correctness is preserved.

**KAL-ARCH-015 — Derived views are rebuildable** Indexes, projections, progress summaries, and UI-friendly normalized views should be reconstructable from authoritative product records and canonical workspace/engine evidence where feasible.

---

# 5. System Context

```text
+---------+       +-------------------------+
| Browser | ----> | Kallula Control Plane   |
+---------+       +-----------+-------------+
                              |
                +-------------+-------------+
                |                           |
                v                           v
       +----------------+          +------------------+
       | Durable State  |          | Run Coordinator  |
       +----------------+          +---------+--------+
                                            |
                                            v
                                  +------------------+
                                  | Siesta Adapter   |
                                  +---------+--------+
                                            |
                                            v
                                  +------------------+
                                  | Execution Worker |
                                  +---------+--------+
                                            |
                                            v
                                  +------------------+
                                  | Project Workspace|
                                  +------------------+
```


At the highest level Kallula sits between a human user and an autonomous software-development engine.

```text
Human
  │
  ▼
Browser
  │
  ▼
Kallula Control Plane
  │
  ├── product state
  ├── authorization
  ├── run commands
  ├── interactions
  ├── normalized events
  ├── integrations
  └── preview control
  │
  ▼
Execution Coordination
  │
  ▼
Engine Adapter
  │
  ▼
Isolated Execution Attempt
  │
  ├── Siesta
  ├── Pi / configured model providers
  ├── development tools
  └── generated application processes
  │
  ▼
Canonical Project Workspace
  │
  ├── Git
  ├── source/tests
  └── Siesta-native state/evidence
```

External systems may include:

- model providers;
- GitHub;
- credential/key-management facilities;
- email/browser notification channels;
- preview ingress/routing infrastructure;
- durable backup storage.

None of those external systems becomes authoritative for Kallula Project or Run state.

---

# 6. Logical Architecture

The required logical components are shown below.

```text
┌───────────────────────────────────────────────────────────────┐
│                        Browser Client                         │
└──────────────────────────────┬────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────┐
│                    Kallula Control Plane                      │
│                                                               │
│  Auth / Projects / Runs / Commands / Interactions / Config    │
│  Events / Artifact Index / Integrations / Preview Control     │
└───────────────┬───────────────────────────────┬───────────────┘
                │                               │
                ▼                               ▼
┌───────────────────────────┐       ┌───────────────────────────┐
│ Durable Control State     │       │ Credential Boundary       │
│ + Normalized Event Journal│       │ + Trusted Integrations    │
└───────────────┬───────────┘       └───────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│                  Run Coordinator / Reconciler                 │
│  command claiming • leases • attempts • heartbeats • recovery│
└──────────────────────────────┬────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────┐
│                         Engine Adapter                        │
│ capabilities • stage/event normalization • interaction bridge│
│ stop/resume • artifact mapping • result translation           │
└──────────────────────────────┬────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────┐
│                    Isolated Execution Worker                  │
│                       Siesta + Pi + tools                     │
└──────────────────────────────┬────────────────────────────────┘
                               │ exclusive writable attachment
                               ▼
┌───────────────────────────────────────────────────────────────┐
│                    Canonical Project Workspace                │
│             source • Git • tests • Siesta native state       │
└──────────────────────────────┬────────────────────────────────┘
                               │
                   ┌───────────┴────────────┐
                   ▼                        ▼
        ┌────────────────────┐   ┌────────────────────────┐
        │ Preview Controller │   │ Export / Git Publishing │
        └────────────────────┘   └────────────────────────┘
```

The diagram intentionally does not say whether these components are processes, modules, containers, or services.

---

# 7. Component Responsibilities

## 7.1 Browser Client

The browser client is responsible for:

- presenting Kallula product state;
- initiating authenticated commands;
- displaying normalized run progress/events;
- answering pending human interactions;
- requesting safe stop/resume;
- browsing files/Git/evidence;
- opening previews;
- configuring supported profiles/environment/credentials;
- reconnecting after network/browser interruption.

The browser client is **not** responsible for:

- maintaining the execution process;
- determining whether an engine operation mechanically succeeded;
- owning pending interaction state;
- storing the only copy of run progress;
- interpreting Siesta checkpoint files;
- deciding that a worker is dead solely from a lost browser stream.

## 7.2 Kallula Control Plane

The Control Plane owns the product-facing lifecycle.

Responsibilities include:

- authentication and authorization;
- Project and Run creation;
- effective configuration snapshot creation;
- durable command acceptance;
- pending interaction storage;
- normalized Run state;
- normalized stage/work-item state;
- event and artifact indexing;
- integration requests;
- preview metadata/control requests;
- run history;
- audit records;
- API responses and live-update fan-out.

The Control Plane must not reimplement Siesta's planning, execution, recovery, review, or verification logic.

## 7.3 Durable Control State

A durable control-state store is authoritative for Kallula product records.

It stores or references:

- users/ownership;
- Projects;
- Runs;
- Execution Attempts;
- accepted run commands;
- run control state;
- normalized stages/work items;
- pending interactions;
- normalized events;
- configuration snapshots;
- engine/adapter identities;
- environment profile references;
- credential metadata/permissions;
- artifact index metadata;
- verified-state records;
- preview metadata;
- integration state;
- audit data.

The exact storage engine is not selected by this document.

## 7.4 Run Coordinator

The Run Coordinator turns durable Kallula intent into execution.

Responsibilities include:

- finding accepted commands that require action;
- obtaining exclusive execution ownership where required;
- creating Execution Attempts;
- starting the worker through the adapter boundary;
- recording attempt heartbeat/liveness;
- forwarding durable interaction answers and stop intents;
- observing worker/adapter exit;
- releasing leases;
- scheduling safe continuation when necessary;
- invoking reconciliation after uncertain failure.

It must be possible to restart the Run Coordinator without losing the user's accepted intent.

## 7.5 Reconciler

Reconciliation is an architectural responsibility even if it initially runs inside the same process as the Run Coordinator.

The Reconciler handles states where Kallula cannot safely infer reality from one component alone.

Examples:

- a Run says `RUNNING` but its execution lease expired;
- a worker process disappeared without a terminal result;
- the web/control process restarted while a worker continued;
- the host restarted and no worker remains;
- a pending interaction exists but no worker is attached;
- the adapter reports a checkpoint newer than Kallula's last normalized event;
- a stop request was recorded but the worker vanished before confirming a boundary.

The Reconciler inspects durable control records plus adapter/workspace evidence and moves the Run to a truthful recoverable state.

## 7.6 Engine Adapter

The Engine Adapter is the only Kallula component allowed to understand Siesta-native execution semantics.

It is responsible for translating between:

```text
Kallula concepts                  Siesta-native concepts
────────────────────────────────────────────────────────────────
Run / Execution Attempt       ↔   pipeline invocation/process
Stage                         ↔   native phase/checkpoint
Work Item                     ↔   Siesta issue
Pending Interaction           ↔   Phase 0 human answer point
Safe Stop Request             ↔   supported Siesta stop mechanism
Engine Checkpoint             ↔   native checkpoint/project state
Artifact class                ↔   native filenames/paths
Agent Slot                    ↔   planner/worker/consultant routes
Verification Result           ↔   Siesta mechanical verdict/evidence
Engine Event                  ↔   structured Siesta lifecycle signal
```

The adapter must expose normalized behavior. It must not cause every Kallula component to understand the right-hand side of this table.

The normative Siesta-specific adapter behavior is defined in [`Kallula — Siesta Engine Adaptation Specification.md`](./Kallula%20%E2%80%94%20Siesta%20Engine%20Adaptation%20Specification.md). That specification may choose concrete Siesta-facing seams but may not redefine the lifecycle/ownership semantics in this document.

## 7.7 Execution Worker

An Execution Worker is the isolated runtime in which an Execution Attempt occurs.

It may contain:

- the pinned Siesta engine revision;
- the compatible Kallula Siesta adapter;
- Pi and related tooling;
- selected model/provider configuration;
- development runtimes/build tools;
- an attached canonical workspace;
- explicitly permitted network/resource capabilities.

The worker is disposable.

The workspace and Kallula control state are not.

## 7.8 Workspace Manager

The Workspace Manager is the conceptual owner of creating, locating, attaching, exporting, backing up, and validating Project workspaces.

Its implementation may initially be simple filesystem logic.

It must guarantee that:

- every Project has a stable workspace identity independent of slug/display name;
- a worker receives the correct workspace;
- a worker crash does not delete the workspace;
- clean export reads from the canonical workspace;
- write access follows the Project execution lease;
- accidental use of an ephemeral worker filesystem as the only project copy is impossible.

## 7.9 Event Journal / Projection Layer

Normalized execution events are durable product data.

The Event Journal stores the ordered history Kallula needs to explain what happened.

UI-specific progress summaries may be projections over that history and current Run records.

The event journal is not a substitute for raw engine evidence. Native logs/artifacts remain available by reference where needed.

## 7.10 Artifact Index

The Artifact Index maps normalized artifact concepts to authoritative evidence.

Examples:

- specification;
- implementation plan;
- engine checkpoint;
- test evidence;
- verification result;
- consultation output;
- runtime logs;
- knowledge graph;
- recovery archive.

The index records metadata and references. It does not need copying every artifact into the control-plane database.

## 7.11 Credential Boundary

Credential storage and trusted integration execution are outside autonomous worker authority by default.

The Control Plane may reference permitted credential names/IDs. Workers receive only explicitly permitted runtime material according to the normative Security & Credentials Design.

## 7.12 Preview Controller

The Preview Controller owns the Kallula lifecycle of generated application previews.

It is conceptually separate from Siesta verification.

It handles:

- requested preview startup;
- service/process discovery results;
- preview lifecycle state;
- health information;
- route metadata;
- stop/restart requests;
- runtime log association.

The physical sandbox, source-snapshot, networking, routing, secret-injection, health, and cleanup model is defined by [`Kallula — Execution Environment & Preview Design.md`](./Kallula%20%E2%80%94%20Execution%20Environment%20%26%20Preview%20Design.md).

## 7.13 Trusted Integration Layer

Operations that require platform credentials and should not be performed by autonomous coding agents belong here.

Examples:

- GitHub repository creation;
- branch pushing;
- pull-request creation;
- notification delivery;
- future deployment-provider actions.

---

# 8. Sources of Truth

Kallula deliberately has more than one authoritative data domain. Correctness depends on knowing which domain owns what.

| Concern | Authoritative source | Derived/indexed elsewhere? |
|---|---|---|
| Project identity/ownership | Kallula control state | UI projections |
| Run control state | Kallula control state | dashboard/live views |
| Run configuration snapshot | Kallula control state | worker launch material |
| Execution-attempt history | Kallula control state | diagnostics |
| Human pending interaction | Kallula control state, correlated to adapter interaction token | UI/live events |
| Normalized event history | Kallula event journal | progress projections |
| Source files | canonical workspace | read-only UI/export |
| Git history | `.git` in canonical workspace | Git UI index/cache |
| Dirty current working tree | canonical workspace | status projection |
| Siesta native checkpoint | canonical workspace / engine-native state | adapter-derived compatibility metadata |
| Siesta project KB | canonical workspace / engine-native KB | normalized Knowledge view/index |
| Raw engine evidence | canonical workspace or dedicated evidence storage | artifact index |
| Last verified project state | Kallula Verified State record referencing exact Git/evidence identity | dashboard/project summary |
| Credential value | protected credential store | never duplicated into ordinary product DB |
| Credential assignment metadata | Kallula control state | UI |
| Preview runtime truth | preview runtime/controller | Kallula preview state projection |
| GitHub remote truth | GitHub | integration status cached in Kallula |

## 8.1 Conflict rule

When two domains disagree, Kallula must not “pick whichever looks newer” generically.

The owner of the relevant concept wins.

Examples:

- If the database says the last verified commit is `abc` but the workspace HEAD is `def`, both may be correct: `abc` is verified; `def` is current.
- If a Run says `RUNNING` but its lease expired and no worker exists, the Run record is stale and must be reconciled; it must not remain indefinitely `RUNNING`.
- If a cached Files view differs from the workspace, the workspace wins.
- If a model says tests passed but test evidence says failed, the mechanical evidence wins.

---

# 9. Core Entity Relationships

The principal system entities are:

```text
User
 └── owns ── Project
               │
               ├── owns ── Canonical Workspace
               │             └── Git + source + engine-native state
               │
               ├── has ── Run *
               │          │
               │          ├── immutable Effective Configuration
               │          ├── Execution Attempt *
               │          ├── Event *
               │          ├── Pending Interaction *
               │          ├── Work Item projection *
               │          └── Artifact reference *
               │
               ├── has ── Verified State (0..1 current pointer + history)
               ├── uses ── Agent Profile default/version
               ├── uses ── Environment Profile default/version
               └── permits ── Credential assignments
```

A Project may have many Runs over time.

A Run may have many Execution Attempts.

Only one Execution Attempt may hold active write ownership of a Project workspace at a time in the initial architecture.

---

# 10. Project Model

A Project is the durable unit of software ownership in Kallula.

A Project outlives any individual Run or worker.

At minimum a Project has:

- stable project ID;
- owner ID;
- display name/metadata;
- origin metadata: new idea or imported repository;
- canonical workspace identity/location reference;
- default engine selection policy;
- default Agent Profile reference;
- default Environment Profile reference;
- engineering preferences;
- permitted credential assignments;
- Run history;
- current Verified State reference where one exists;
- archival status if/when archiving is implemented.

## 10.1 Project lifecycle

The initial architecture does not need a complicated Project state machine.

A Project is primarily **active** or **archived/deleted according to future retention policy**.

Operational attention such as `running`, `waiting`, `failed`, and `completed` belongs to Runs and is surfaced on the Project summary as derived information.

This prevents Project lifecycle from duplicating Run lifecycle.

---

# 11. Run Model

A Run represents one logical autonomous execution objective against a Project under one immutable effective configuration.

Examples:

- initial project build;
- continuation after a safe stop;
- recovery after a crashed worker while pursuing the same objective;
- a later feature implementation, when created as a new Run;
- a maintenance/refactor task, when created as a new Run.

## 11.1 Run identity is logical, not process identity

A Run is not a Unix process, container, VM, or worker.

A Run may survive multiple worker lifetimes.

This is essential for crash recovery and truthful history.

## 11.2 Immutable effective configuration

Before a Run becomes executable, Kallula materializes an effective configuration snapshot containing enough information to attribute execution reproducibly.

At minimum:

- engine identity/revision;
- adapter identity/version;
- capability-manifest identity/hash where appropriate;
- agent slot configuration;
- provider/model assignments;
- supported reasoning/tool settings;
- relevant user instructions/engineering preferences snapshot;
- skill identities/versions/content hashes where required;
- environment profile/version;
- permitted credential identifiers/names, never values;
- project starting Git identity/status;
- creation timestamps.

This snapshot does not mutate after the Run starts.

## 11.3 Resume vs new Run

This document resolves an ambiguity from the PRD:

> **Resume continues the same logical Run when Kallula is continuing the same execution objective from the same immutable Run configuration and compatible engine-native checkpoint/workspace state.**

A resumed Run creates a **new Execution Attempt**, not a new Run.

A **new Run** is created when the logical objective or effective execution configuration is intentionally changed in a way that should create a new historical execution boundary.

Examples that normally create a new Run:

- “Now add multi-user support.”
- switching to a new engine/profile for a new maintenance operation;
- a deliberate requirement-change workflow after the current Run has been stopped/closed;
- a new imported-repository task.

Examples that normally remain the same Run:

- resuming after user-requested safe stop;
- continuing after `WAITING_FOR_HUMAN`;
- relaunching after a crashed worker with compatible checkpoint state;
- retrying an infrastructure-level startup failure before engine work begins.

This model allows Kallula to preserve both logical user intent and physical execution history.

---

# 12. Execution Attempt Model

An Execution Attempt is one concrete worker ownership period for a Run.

It exists to answer questions that Run state alone cannot answer cleanly:

- Which worker process actually executed this segment?
- When did it start and stop?
- Was it lost due to infrastructure failure?
- Did a resume launch a fresh process?
- Which logs belong to which process lifetime?
- Was a command acknowledged by the same attempt or a later one?

At minimum an Execution Attempt records:

- attempt ID;
- Run ID;
- ordinal/sequence within the Run;
- worker identity/reference;
- adapter/engine identity actually launched;
- start/end timestamps;
- heartbeat/liveness metadata;
- attempt terminal reason;
- raw log/evidence references;
- lease ownership metadata;
- checkpoint/evidence observed at start and end where useful.

Execution Attempts are primarily an operational/diagnostic concept. The normal user experience may present them as one continuous Run unless the distinction matters.

---

# 13. Run Control State Machine

```text
QUEUED -> STARTING -> RUNNING ---------------------------> COMPLETED
                       |   \
                       |    \-> STOP_REQUESTED -> STOPPED
                       |                           |
                       |                           +-> QUEUED (resume)
                       |
                       +-> WAITING_FOR_HUMAN
                               |
                               +-> QUEUED (answer)

STARTING / RUNNING / STOP_REQUESTED may also -> FAILED
FAILED may -> QUEUED only when resume is allowed
```


Kallula control state is separate from engine stage.

The initial Run states are:

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

No additional public state is required at this stage.

Infrastructure uncertainty is represented through attempt state, lease state, failure metadata, and reconciliation rather than prematurely adding many user-facing Run states.

## 13.1 State meanings

### `QUEUED`

A durable execution or continuation intent exists, but no active Execution Attempt has yet obtained ownership.

### `STARTING`

An Execution Attempt owns the Run/project lease and is preparing the worker/adapter/engine but meaningful engine execution has not yet been confirmed.

### `RUNNING`

The pinned engine is actively progressing or is alive in a state that does not currently require human input.

### `WAITING_FOR_HUMAN`

The engine has reached an interaction point whose answer must come from Kallula. The pending interaction is durable.

The underlying worker may either remain alive/suspended or exit cleanly according to adapter design. Run state is the same in either case.

### `STOP_REQUESTED`

Kallula has durably accepted a safe-stop request, but the engine has not yet confirmed a supported safe boundary.

### `STOPPED`

The engine/adapter has confirmed execution is no longer active at a resumable or otherwise deliberate stop boundary.

### `FAILED`

Execution cannot currently continue automatically because an engine, adapter, worker, infrastructure, or compatibility failure requires recovery/retry/user action.

`FAILED` does not erase recoverability. Recovery metadata states whether an explicit resume/retry is allowed.

### `COMPLETED`

The logical Run has reached its terminal result and Kallula has persisted the translated engine result/evidence.

`COMPLETED` is terminal for that Run. Later work creates another Run.

## 13.2 Allowed transitions

The principal transitions are:

```text
QUEUED ───────────────► STARTING
STARTING ─────────────► RUNNING
STARTING ─────────────► FAILED

RUNNING ──────────────► WAITING_FOR_HUMAN
WAITING_FOR_HUMAN ────► QUEUED or RUNNING

RUNNING ──────────────► STOP_REQUESTED
WAITING_FOR_HUMAN ────► STOP_REQUESTED
STOP_REQUESTED ───────► STOPPED
STOP_REQUESTED ───────► FAILED

RUNNING ──────────────► COMPLETED
RUNNING ──────────────► FAILED

STOPPED ──────────────► QUEUED        (explicit resume)
FAILED ───────────────► QUEUED        (explicit recovery/retry when permitted)

COMPLETED ────────────X no continuation transition
```

`WAITING_FOR_HUMAN -> RUNNING` is allowed when the same live attempt can safely consume the answer.

`WAITING_FOR_HUMAN -> QUEUED` is allowed when the waiting implementation suspends/exits and the answer requires a new attempt to continue.

The UI need not expose this implementation difference.

## 13.3 Forbidden transitions

Examples of transitions that must not occur implicitly:

- `FAILED -> COMPLETED` because a stale frontend reconnects;
- `STOP_REQUESTED -> STOPPED` merely because the worker process disappeared;
- `WAITING_FOR_HUMAN -> RUNNING` without a valid answer/delegation event;
- `COMPLETED -> RUNNING` to implement new work;
- any state -> `COMPLETED` based solely on process exit code when engine semantics disagree.

---

# 14. Execution Attempt State Machine

Execution Attempt state is internal/operational and may be more precise than Run state.

Recommended conceptual states are:

```text
ALLOCATED
STARTING
ACTIVE
SUSPENDED
EXITED
LOST
```

This is an architecture model, not yet a mandated API enum.

- `ALLOCATED`: attempt record exists and lease was/will be obtained.
- `STARTING`: worker launch in progress.
- `ACTIVE`: worker/adapter execution is alive.
- `SUSPENDED`: worker is intentionally quiescent while preserving resumable context, if supported.
- `EXITED`: worker ended with an observed/translated exit condition.
- `LOST`: Kallula lost execution ownership/liveness without a trustworthy terminal handshake.

A `LOST` attempt triggers reconciliation. It does not directly imply Run `FAILED`, `STOPPED`, or `COMPLETED` until evidence is inspected.

---

# 15. Engine Stage Model

Stage is descriptive engine progress, not control state.

The initial normalized stage vocabulary is about:

```text
REQUIREMENTS
SPECIFICATION
PLANNING
EXECUTION
REVIEW
VERIFICATION
LEARNING
COMPLETED
```

The exact persisted representation may permit custom/unknown engine stage identifiers so future Siesta revisions can add or change topology without requiring a Kallula schema rewrite.

## 15.1 Stage contract

A normalized Stage record/event should carry:

- stable Kallula normalized category where one exists;
- engine-native stage identifier;
- human-readable label;
- sequence/order hint where available;
- stage status;
- timestamps;
- optional parent/work-item context;
- native evidence reference.

## 15.2 Stage topology is data, not UI code

The frontend must not hard-code `phase-0 ... phase-7`.

The adapter provides the current normalized topology/capability information.

If a later Siesta version inserts an architecture-analysis stage between planning and execution, the rest of Kallula should primarily receive a new stage/event mapping rather than require database or UI redesign.

---

# 16. Work Item Model

A Work Item is Kallula's normalized representation of a planned/executed unit of work.

For current Siesta, a Work Item corresponds to an issue parsed/identified by the adapter.

A Work Item may expose:

- normalized work-item ID within the Run/plan;
- engine-native ID/reference;
- title/description;
- acceptance criteria;
- dependencies;
- normalized status;
- attempts/retries;
- consultations/proxy decisions;
- test evidence;
- related commit(s);
- blocker information.

Kallula must not make `issues.md` itself the public API contract.

The adapter may initially derive Work Items from that artifact while upstream structured support is introduced.

---

# 17. Human Interaction Model

A Pending Interaction is durable Kallula product state.

The browser must never be the only holder of an unanswered engine question.

## 17.1 Interaction states

The conceptual lifecycle is:

```text
PENDING
  ├──► ANSWERED
  ├──► DELEGATED
  └──► CLOSED
```

`CLOSED` covers cases where the Run fails/stops/completes or the interaction is superseded before a user answer can be applied.

## 17.2 Interaction identity

Every interaction must have a stable Kallula interaction ID and an adapter/native correlation token sufficient to ensure an answer is delivered to the correct waiting engine context.

## 17.3 Answer idempotency

Submitting the same answer twice because of browser retry/network uncertainty must not cause the engine to consume it twice.

The first accepted terminal response for a `PENDING` interaction wins. Later duplicate requests return the already-recorded result or an explicit conflict; they do not produce a second engine answer.

## 17.4 One active interactive question in v1

Current Siesta interview behavior is one-question-at-a-time. Kallula v1 may therefore enforce at most one active pending engine interaction per Run.

The interaction model itself must not require that limitation permanently; future engine capabilities may allow multiple independent requests.

## 17.5 Waiting implementation is adapter-specific

Kallula does not need a worker process to remain alive while waiting.

The adapter may support either:

1. a suspended/live engine process awaiting an external answer; or
2. a durable handoff where the engine stops/quiesces and a later attempt resumes from checkpoint plus answer.

The product-visible state is still `WAITING_FOR_HUMAN`.

---

# 18. Safe Stop Model

Safe stop is a cooperative engine operation, not a generic process kill.

## 18.1 Command semantics

When the user requests safe stop:

1. Kallula durably records the stop command.
2. Run state becomes `STOP_REQUESTED`.
3. The Run Coordinator/adapter delivers the stop intent to the current attempt or prepares it for the next supported boundary.
4. The engine continues until it reaches a native safe boundary.
5. The adapter emits/returns stop confirmation with relevant checkpoint/evidence.
6. Kallula records the terminal attempt state and changes Run state to `STOPPED`.

## 18.2 Current Siesta mapping

Current Siesta may implement this through its issue-boundary `stop.md` semantics.

Only the adapter may know that.

The Control Plane stores `safe stop requested`, not `create stop.md`.

## 18.3 Hard termination

Emergency force termination is a distinct future/admin safety mechanism and is not equivalent to safe stop.

If infrastructure terminates a worker unexpectedly, reconciliation determines Run state; Kallula must not label that `STOPPED` automatically.

---

# 19. Resume and Recovery Model

Resume is permitted only when all of the following are true:

1. the Project workspace exists and is coherent enough to inspect;
2. the Run's immutable configuration snapshot exists;
3. the pinned engine/adapter needed for the Run is available, or a formally compatible replacement has been validated;
4. the adapter reports that native checkpoint/workspace state is resumable;
5. no other active Project execution lease exists;
6. any pending interaction requirements are satisfied or explicitly carried forward;
7. Kallula has not marked the Run `COMPLETED`.

## 19.1 Resume creates an Execution Attempt

The user-visible Run continues.

A new attempt is created and linked to the existing Run.

## 19.2 Recovery from `FAILED`

A Run may move from `FAILED` to `QUEUED` only through an explicit recovery/retry action that has passed compatibility checks.

The previous failed attempt remains immutable historical evidence.

## 19.3 Recovery from uncertain worker loss

If an attempt is `LOST`, the Reconciler must inspect:

- whether any worker still owns/uses the workspace;
- execution lease expiry;
- native checkpoint state;
- current Git/worktree state;
- adapter recovery evidence;
- last durable normalized event;
- terminal/result artifacts if they exist.

Only after this inspection may Kallula decide whether the logical Run is:

- still active under another known attempt;
- resumable and should become `FAILED` with recovery allowed;
- safely stopped according to engine evidence;
- actually completed with valid terminal evidence;
- unrecoverable/incompatible.

---

# 20. Execution Ownership and Leases

Kallula needs a concurrency mechanism even in a single-user deployment because HTTP requests, coordinator processes, retries, and crashes can overlap.

The architecture therefore requires an **exclusive Project execution lease**.

## 20.1 Lease purpose

The lease guarantees that at most one autonomous Execution Attempt has writable ownership of the canonical Project workspace at a time.

It prevents:

- duplicate workers started by retrying the same command;
- two Run Coordinators simultaneously launching the same Run;
- two Runs modifying one Project workspace concurrently;
- crash-recovery code racing a still-live worker.

## 20.2 Lease properties

The logical lease records at least:

- Project ID;
- Run ID;
- Execution Attempt ID;
- owner/worker identity;
- acquisition timestamp;
- last heartbeat/renewal;
- expiry/validity semantics.

Exact schema/storage primitives are deferred.

## 20.3 Lease expiry is not proof of worker death

Lease expiry means Kallula no longer has trustworthy ownership confirmation.

It triggers reconciliation before another writer is started.

Where the runtime can independently prove the old worker is terminated, reconciliation may safely release ownership.

## 20.4 Read access

Read-only source/event/UI access may occur while a worker holds the write lease.

Operations that mutate the workspace outside the engine—such as browser editing—are deferred because they would require coordination with this lease model.

---

# 21. Durable Command Model

User intent that affects asynchronous execution must be represented durably.

Examples include:

- start Run;
- answer interaction;
- request safe stop;
- resume/retry Run;
- start/stop preview;
- publish to GitHub.

This does not need a separate message-broker product in the initial implementation.

A database-backed command record or equivalent durable state transition can satisfy the requirement.

## 21.1 Command properties

A command should conceptually include:

- command ID;
- target entity;
- command type;
- authenticated actor;
- creation time;
- idempotency identity where relevant;
- command parameters/reference;
- status/outcome;
- processing attempt metadata.

## 21.2 Transactional acceptance

The product should not tell the user “stop requested” or “resume queued” until that intent is durably stored.

## 21.3 At-least-once processing, idempotent effects

The architecture assumes a command may be observed/processed more than once after crashes or retries.

Handlers therefore must make repeated processing safe.

Examples:

- processing `START_RUN` twice cannot create two active workers;
- processing `ANSWER_INTERACTION` twice cannot feed two answers;
- processing `REQUEST_STOP` twice remains one stop intention;
- replaying a completion event cannot create duplicate verified-state records.

This approach provides robustness without requiring an exactly-once messaging system.

---

# 22. Normalized Event Model

Events exist for three purposes:

1. durable history for the user;
2. reconstruction/projection of execution progress;
3. diagnostics and auditability.

## 22.1 Event identity

Every normalized event must have a unique Kallula event ID.

Engine-originated events should also carry an adapter/native correlation identity when one exists.

## 22.2 Event ordering

Kallula guarantees a stable append order **within a Run as observed by the Control Plane**.

This should be represented by a monotonically increasing Run-local sequence assigned at durable ingestion.

Engine-native timestamps may be preserved, but timestamp ordering alone is not authoritative because clocks and buffered delivery can disagree.

## 22.3 Idempotent ingestion

The adapter/event ingestion boundary must support deduplication using a source event identity or stable idempotency key whenever an event may be retried.

For the reviewed Siesta baseline, [`Kallula — Siesta Engine Adaptation Specification.md`](./Kallula%20%E2%80%94%20Siesta%20Engine%20Adaptation%20Specification.md) defines the initial stable source key as **Execution Attempt ID + adapter-assigned Attempt-local event sequence**, with native phase/work-item/correlation metadata retained for reconciliation.

## 22.4 Event source

Events should identify a source domain such as:

- `control-plane`;
- `coordinator`;
- `adapter`;
- `engine`;
- `preview`;
- `integration`.

This is diagnostic metadata, not necessarily a user-facing label.

## 22.5 Event payload stability

The normalized event envelope should remain stable while allowing typed payload evolution.

The frontend should not parse raw Siesta console strings to determine product state.

## 22.6 State transition events

Meaningful Run state transitions should have corresponding durable events.

The authoritative current state remains the Run record; the event history explains how it was reached.

## 22.7 Raw evidence retention

Normalized events may reference raw output/log/artifact evidence.

Normalization must not discard data required to debug or verify a decision.

---

# 23. Artifact Model

An Artifact is an indexed piece of evidence or product output with a normalized class and an authoritative backing location/reference.

## 23.1 Artifact metadata

The architecture should support metadata such as:

- artifact ID;
- Project ID;
- Run/Attempt/Work Item association where relevant;
- normalized artifact class;
- native artifact identity/path;
- media/type information;
- content hash where useful;
- created/updated timestamps;
- sensitivity/visibility classification;
- engine/adapter source;
- version/generation metadata.

## 23.2 Artifact content location

Artifact bytes/content do not need to live in the control database.

Initially, many artifacts may simply point into the canonical workspace.

Later, large immutable logs/evidence may move to dedicated object/evidence storage without changing the normalized artifact contract.

## 23.3 Engine upgrade behavior

Native filenames may change across Siesta revisions.

Only adapter mappings change.

Historical Artifact records retain their native mapping and engine/adapter identities so history remains interpretable.

---

# 24. Workspace and Git Model

## 24.1 Workspace identity

The workspace path/storage key is derived from a stable internal Project identity, not from a human display name or slug alone.

## 24.2 Workspace durability

The workspace must survive:

- browser disconnect;
- web/control-plane restart;
- Run Coordinator restart;
- worker termination;
- normal host/service restarts within the supported deployment model.

## 24.3 Git authority

Git inside the canonical workspace is the authoritative source of commit history.

Kallula may cache/index commit metadata for UI speed, but it must not manufacture a separate competing Git history.

## 24.4 Dirty workspace

A Run may legitimately have a dirty working tree during active execution.

Kallula must represent this as current/unverified state, not attempt to force every moment into a commit.

## 24.5 Workspace snapshotting

This architecture does not need full filesystem snapshots for every Run.

Where a Run begins, Kallula records the starting Git identity and relevant dirty-state metadata.

If future functionality requires snapshot/branch/worktree isolation between concurrent Runs, it must be deliberately designed rather than inferred here.

## 24.6 Existing repository import

Import initializes the Project's canonical workspace from the selected repository/branch/revision while preserving Git history.

Exact remote auth and branch/PR policy remain separate design topics.

---

# 25. Verified State Model

Verified State is a first-class durable Project concept, not just a badge on the latest Run.

A Verified State record must identify enough evidence to answer:

- exactly which source state was verified;
- which Run produced/verified it;
- which engine/adapter/configuration performed verification;
- which verification evidence supports the claim;
- when it was verified.

## 25.1 Minimum identity

For Git-backed projects the verified source identity should normally include an exact commit ID.

If verification can occur against dirty/uncommitted state in some future engine mode, that mode requires an equally strong content identity; the initial architecture should prefer a committed verified state.

## 25.2 Project pointer

A Project may maintain a convenient pointer to its latest known Verified State.

Historical Verified State records should remain attributable to their Runs.

## 25.3 Staleness

If the live workspace no longer matches the verified source identity, the Verified State is **not invalidated**, but it is no longer the current workspace state.

The UI should say conceptually:

```text
Current workspace: newer/unverified changes exist
Last verified: commit abc123, Run #12, verification passed
```

## 25.4 Verification truth

The adapter translates Siesta's real verification result and mechanical evidence.

Kallula does not create a Verified State merely because:

- the worker exited with status 0;
- a model said `passed` in prose;
- a preview responds successfully;
- a previous Run had passed tests.

---

# 26. Preview State Model

Preview lifecycle is independent of Run control state and verification.

Normalized preview states are:

```text
NOT_RUNNABLE
STARTING
AVAILABLE
UNAVAILABLE
FAILED
STOPPED
```

A Project may have a preview while a Run continues.

A Run may complete with no preview.

A preview may be healthy while verification fails.

A verified project may later have an unavailable preview because the runtime process stopped.

This separation must be represented in the data model and frontend.

---

# 27. Start-Run Flow

The canonical start flow is:

```text
User requests start
    ↓
Control Plane validates Project + requested defaults
    ↓
Engine installation/capabilities resolved
    ↓
Effective immutable Run configuration materialized
    ↓
Run created as QUEUED
    ↓
START command durably recorded
    ↓
HTTP request may end
    ↓
Run Coordinator claims command/Project execution lease
    ↓
Execution Attempt created
    ↓
Run becomes STARTING
    ↓
Workspace attached/validated
    ↓
Engine Adapter launches pinned Siesta in isolated worker
    ↓
Adapter confirms meaningful engine execution
    ↓
Run becomes RUNNING
    ↓
Events/stages/artifacts flow asynchronously
```

If any failure occurs before the engine is safely active, the attempt is recorded and the Run becomes `FAILED` or remains/re-enters `QUEUED` only under an explicit bounded infrastructure retry policy defined later.

Kallula must not create an infinite startup retry loop implicitly.

---

# 28. Human-Interaction Flow

```text
Siesta reaches human question
    ↓
Adapter receives structured interaction request
    ↓
Kallula creates Pending Interaction (PENDING)
    ↓
Question event + context persisted
    ↓
Run becomes WAITING_FOR_HUMAN
    ↓
Browser may disconnect for minutes/hours/days
    ↓
User opens project and submits answer
    ↓
Control Plane atomically marks interaction ANSWERED
and records answer command/idempotency identity
    ↓
Coordinator/adapter consumes answer
    ↓
Same attempt continues OR new attempt is queued
according to adapter capability
    ↓
Run returns to RUNNING when execution actually resumes
```

The answer must not disappear if worker continuation fails. The durable interaction record remains evidence that the human answered; the adapter/recovery logic decides how that answer is safely re-applied or recognized as already consumed.

---

# 29. Safe-Stop Flow

```text
User requests safe stop
    ↓
Control Plane persists stop command
    ↓
Run becomes STOP_REQUESTED
    ↓
Coordinator/adapter observes command
    ↓
Adapter maps to Siesta-native stop mechanism
    ↓
Engine reaches supported safe boundary
    ↓
Native checkpoint/evidence updated
    ↓
Adapter confirms stopped semantics
    ↓
Attempt exits/suspends intentionally
    ↓
Run becomes STOPPED
    ↓
Lease released
```

If the worker disappears after `STOP_REQUESTED` but before confirmation, Kallula reconciles. It does not assume the safe boundary was reached.

---

# 30. Resume Flow

```text
User requests resume
    ↓
Run must be STOPPED or recoverable FAILED
    ↓
Kallula validates immutable Run configuration
    ↓
Pinned engine/adapter availability checked
    ↓
Adapter inspects native checkpoint/workspace compatibility
    ↓
No active Project write lease confirmed
    ↓
RESUME command persisted
    ↓
Run becomes QUEUED
    ↓
New Execution Attempt acquires lease
    ↓
Run becomes STARTING
    ↓
Adapter resumes against SAME canonical workspace
    ↓
Engine confirms continuation
    ↓
Run becomes RUNNING
```

No new prompt-derived Project is created.

No stale database copy of source is used.

No automatic engine upgrade is performed as part of resume.

---

# 31. Completion Flow

```text
Engine reaches native terminal point
    ↓
Adapter inspects engine result + verification evidence
    ↓
Adapter emits normalized terminal result
    ↓
Coordinator persists result/evidence references
    ↓
If verification requirements passed:
    create/update Verified State reference
    ↓
Execution Attempt exits normally
    ↓
Run becomes COMPLETED
    ↓
Lease released
    ↓
Optional result actions become available
```

A Run may be `COMPLETED` with a result that is not verified only if the product semantics explicitly support an unverified terminal outcome. In that case the UI must clearly show that no new Verified State was created.

Current Siesta terminal behavior, verification mapping, and engine outcomes are defined in [`Kallula — Siesta Engine Adaptation Specification.md`](./Kallula%20%E2%80%94%20Siesta%20Engine%20Adaptation%20Specification.md), including the distinction between safe stop, verified completion, resumable incomplete/unverified execution, and failure.

---

# 32. Failure Model

Failure is classified by domain because recovery differs.

## 32.1 Control-plane failure

Examples:

- web process crash;
- API process restart;
- temporary database connectivity failure.

Expected behavior:

- accepted durable commands survive;
- worker execution may continue if independent;
- live browser updates reconnect/replay from durable history;
- coordinator/reconciler restores orchestration.

## 32.2 Coordinator failure

A coordinator may die after creating an attempt or before updating state.

Lease/heartbeat plus reconciliation prevent duplicate ownership and recover truthful state.

## 32.3 Worker infrastructure failure

Examples:

- process/container termination;
- host resource exhaustion;
- lost runtime.

The attempt becomes uncertain/lost; Run state is reconciled using workspace/engine evidence.

## 32.4 Engine failure

Examples:

- Siesta exception;
- impossible checkpoint state;
- recovery gate failure;
- review/verification failure according to engine semantics.

The adapter produces normalized failure details and evidence. Kallula does not mask the failure.

## 32.5 Model/provider failure

Model timeout/routing failures are primarily engine concerns while they occur inside Siesta's bounded recovery semantics.

If the engine ultimately fails or blocks, Kallula receives the normalized result/evidence.

Kallula may separately expose provider diagnostics where useful.

## 32.6 Workspace failure

Examples:

- missing/corrupt workspace;
- inaccessible durable storage;
- Git corruption;
- permissions failure.

This is a Kallula infrastructure failure with potentially severe recoverability impact. The Run must not be restarted against an empty replacement workspace as though nothing happened.

## 32.7 Compatibility failure

If the required pinned engine/adapter is unavailable and compatibility with another version is unproven, the Run fails closed for resume.

The workspace remains available for inspection/export/recovery work.

---

# 33. Crash Recovery and Reconciliation

## 33.1 Startup reconciliation

Whenever the Run Coordinator starts, it must inspect non-terminal Runs that claim active execution.

At minimum it considers:

- current Run state;
- active lease record;
- lease heartbeat/expiry;
- known worker liveness if observable;
- latest attempt state;
- latest normalized event;
- pending interactions;
- adapter-inspected engine checkpoint/result evidence.

## 33.2 No blind replay

The coordinator must not simply replay every unacknowledged start/resume command after restart without checking whether an attempt already exists or engine work already progressed.

## 33.3 Recovery outcomes

Reconciliation may conclude:

- continue observing existing active attempt;
- restore a stale UI/control projection from confirmed attempt state;
- mark the prior attempt `LOST` and Run `FAILED` but resumable;
- recognize durable `WAITING_FOR_HUMAN` state;
- recognize confirmed safe stop;
- recognize actual engine completion and finalize product state;
- mark incompatible/unrecoverable failure.

## 33.4 Human visibility

When recovery changes user-visible Run state, a durable event should explain what happened.

Examples:

- “Worker process was lost; checkpoint is resumable.”
- “Recovered pending requirements question after service restart.”
- “Run could not resume because the pinned engine revision is unavailable.”

---

# 34. Run and Project Concurrency

## 34.1 Initial rule

A Project may have many historical Runs but only one Run may actively own its canonical workspace for autonomous mutation at a time.

## 34.2 Starting another Run while one is active

The initial product should reject or defer the second mutating Run rather than create hidden worktrees/branches automatically.

This is intentionally conservative.

## 34.3 Read-only concurrent operations

The following may generally coexist with active execution subject to filesystem/runtime safety:

- viewing source;
- viewing Git history;
- viewing events/artifacts;
- reading logs;
- downloading a consistent clean export if the export semantics define the captured point correctly;
- viewing a preview.

Any operation requiring a stable snapshot while the workspace is changing must explicitly define whether it reads HEAD, last verified commit, or a temporary snapshot.

## 34.4 Future parallelism

Parallel multi-agent issue execution, multiple concurrent Runs, or browser editing require a different workspace/branch/worktree coordination design and remain deferred.

---

# 35. Engine Installation and Version Model

An Engine Installation is a Kallula-recognized executable combination of:

- engine family (`siesta` initially);
- exact engine revision/version;
- compatible adapter version;
- capability manifest;
- compatibility/test status;
- runtime dependency metadata needed for launch.

## 35.1 Default selection

Kallula may have a current default supported Siesta installation for **new Runs**.

Changing the default does not change existing Runs.

## 35.2 Run pinning

Every Run pins an Engine Installation identity in its configuration snapshot.

## 35.3 Historical interpretation

Historical normalized events/artifacts remain tagged with the engine/adapter identities that produced them.

## 35.4 Resume behavior

Resume uses the pinned installation when available.

If a newer adapter/engine claims checkpoint compatibility, that compatibility must be established through the launch/state-format/resume compatibility model and compatibility suite defined in [`Kallula — Siesta Engine Adaptation Specification.md`](./Kallula%20%E2%80%94%20Siesta%20Engine%20Adaptation%20Specification.md). Kallula does not assume semantic-version similarity means resumability.

---

# 36. Engine Upgrade Architecture

Engine upgrades are explicit control-plane operations, not incidental package updates.

The architecture is:

```text
New Siesta revision discovered/selected
    ↓
Build/register candidate Engine Installation
    ↓
Adapter introspection succeeds
    ↓
Capability manifest generated/validated
    ↓
Compatibility suite executed
    ↓
Artifact/stage/agent-slot mappings validated
    ↓
Candidate marked SUPPORTED or REJECTED
    ↓
Optional: make supported candidate default for NEW Runs
```

## 36.1 Existing active Runs

Active Runs remain pinned. They are never silently migrated mid-execution.

## 36.2 Stopped/failed Runs

Stopped/failed Runs resume on their pinned engine/adapter unless a formally validated checkpoint-compatibility path exists.

## 36.3 Historical Runs

Historical Runs are never rewritten to claim they used the new engine.

## 36.4 UI adaptation

If the new engine adds capabilities or stages, UI behavior derives from its capability/normalized metadata.

The frontend should not need a source-code change merely because a Siesta phase number changed or a native artifact filename was renamed.

## 36.5 Schema evolution

Normalized Kallula contracts should be additive/evolvable.

If an engine introduces a concept Kallula genuinely cannot represent, Kallula may introduce a new normalized concept deliberately. This is preferable to prematurely inventing a fully generic engine abstraction today.

---

# 37. Capability Model

Capabilities describe what the pinned Engine Installation can do through its adapter.

Examples include:

- interactive requirements;
- autonomous requirements mode;
- safe stop;
- resume;
- structured stages;
- structured work items;
- test evidence;
- verification evidence;
- agent configuration slots;
- skill configuration visibility;
- environment hints;
- preview hints;
- checkpoint compatibility inspection.

Capabilities should be versioned/identified with the engine installation.

The Control Plane uses capabilities for validation.

The browser uses capabilities for presentation.

Neither should infer capability solely from a Siesta version string. The current Siesta manifest requirements and baseline capability declaration are specified in [`Kallula — Siesta Engine Adaptation Specification.md`](./Kallula%20%E2%80%94%20Siesta%20Engine%20Adaptation%20Specification.md).

---

# 38. Agent Configuration Architecture

Kallula's domain model uses **Agent Slots**, not hard-coded permanent roles.

Current Siesta exposes slots mapping to Planner, Worker, and Consultant.

The Engine Installation capability/configuration manifest describes:

- slot identifier;
- display name/purpose;
- supported provider/model fields;
- supported thinking/reasoning values;
- supported skills/options;
- locked protocol configuration;
- user-editable instruction fields;
- validation constraints.

Agent Profiles store Kallula-level values against those normalized slots plus engine-specific validated extensions when necessary.

A Run stores the resolved effective snapshot.

If a future Siesta release splits Reviewer into a dedicated configurable route, the adapter exposes another slot; the rest of the system does not need to redefine the Project or Run model. The reviewed baseline's Planner/Worker/Consultant mapping and supported configuration fields are specified in [`Kallula — Siesta Engine Adaptation Specification.md`](./Kallula%20%E2%80%94%20Siesta%20Engine%20Adaptation%20Specification.md).

---

# 39. Self-Learning and Mutable Engine Assets

Current Siesta may mutate selected factory skills during learning.

That is incompatible with naïvely treating a shared skill directory as immutable Run configuration.

Architecturally:

1. a Run must know which skill content/version it began with;
2. active execution must not silently switch to unrelated shared skill changes made by another Run;
3. learner-produced changes must be attributable to the Run/Attempt that proposed/applied them;
4. historical Runs must remain explainable;
5. the initial hosted design should prefer run/project-scoped or versioned skill material over uncontrolled shared global mutation.

For the reviewed baseline, [`Kallula — Siesta Engine Adaptation Specification.md`](./Kallula%20%E2%80%94%20Siesta%20Engine%20Adaptation%20Specification.md) resolves the initial mechanism as a **Run-scoped mutable engine runtime** derived from an immutable Engine Installation: factory-skill mutations and global learning context are isolated to the Run and reused by its resumed Attempts. Automatic promotion into shared cross-Run skill/global-memory state remains deferred.

This architecture still does not mandate a Git repo per skill, database blob store, or approval workflow; the physical persistence mechanism remains an implementation decision.

---

# 40. Control-Plane Persistence Semantics

## 40.1 Transactional boundaries

Operations that create internally dependent records should be durable atomically where practical.

Examples:

- Run + immutable configuration snapshot + initial start command;
- Pending Interaction + `WAITING_FOR_HUMAN` transition + interaction event;
- accepted answer + interaction terminal state + answer command;
- safe-stop command + `STOP_REQUESTED` transition;
- terminal result + `COMPLETED` transition + Verified State pointer when appropriate.

The exact database transaction implementation is deferred.

## 40.2 Optimistic concurrency

User/control operations should detect stale updates to mutable control records instead of silently overwriting newer state.

The exact row-version/compare-and-set mechanism is an API/data-design decision.

## 40.3 Workspace changes are not database transactions

Kallula cannot atomically transact a filesystem/Git mutation and a database row using an ordinary single database transaction.

Therefore the architecture relies on:

- durable events/evidence;
- idempotent updates;
- explicit checkpoints;
- reconciliation.

The system must be designed for small windows where the workspace advanced but Kallula has not yet recorded the corresponding normalized state, or vice versa.

## 40.4 Do not mirror source into database

The database should not become the canonical store for source files solely to simplify API access.

Source is read from the workspace or an explicit immutable snapshot/export.

---

# 41. Live Update Architecture

Live updates are a projection of durable control state/events.

The transport may be SSE, WebSocket, long polling, or another appropriate mechanism chosen later.

The architectural requirements are:

1. event delivery to the browser may be transient;
2. event history in the backend is durable;
3. the client can reconnect from a known Run-local event sequence/cursor;
4. missing live messages can be replayed/read from durable history;
5. live transport failure does not change Run state;
6. frontend state can be rehydrated from backend APIs without relying on an in-memory stream.

This deliberately decouples “live-feeling UI” from “reliable execution state.”

---

# 42. Security Trust Boundaries at Architecture Level

> **Normative security reference:** [`Kallula — Security & Credentials Design.md`](./Kallula%20%E2%80%94%20Security%20%26%20Credentials%20Design.md) now turns these architecture-level boundaries into concrete credential domains, encryption/key rules, browser/session requirements, worker/provider/GitHub exposure rules, Preview isolation constraints, redaction, auditability, and security acceptance tests.

Detailed threat modeling is deferred, but component trust boundaries are fixed now.

## 42.1 Browser is untrusted input

All user-provided configuration, answers, filenames/paths, Git targets, and commands require server-side authorization and validation.

## 42.2 Autonomous worker is not trusted with control-plane authority

The worker must not receive, by default:

- Kallula database credentials;
- root encryption keys;
- broad GitHub tokens;
- host SSH keys;
- Docker daemon control;
- credentials for other Projects;
- infrastructure control-plane credentials.

## 42.3 Adapter is privileged relative to the engine

The adapter/worker launcher may need access to Kallula-issued identifiers, workspace paths, and constrained execution configuration.

It should expose only what the engine requires.

## 42.4 Preview application is untrusted workload

Generated applications must not share the Control Plane's trust boundary simply because Kallula created them.

## 42.5 Trusted integrations are separate from coding agents

Publishing to GitHub or future cloud providers is performed by trusted Kallula code after user authorization, not by giving broad platform tokens to the autonomous worker.

---

# 43. Initial Deployment Model

The architecture explicitly permits a simple initial deployment.

> **Normative runtime reference:** [`Kallula — Execution Environment & Preview Design.md`](./Kallula%20%E2%80%94%20Execution%20Environment%20%26%20Preview%20Design.md) specifies how this co-located model must isolate workloads and Preview even when all trusted services live on one host.

A valid first deployment may co-locate:

- Control Plane API;
- Run Coordinator/Reconciler;
- persistent control database;
- durable workspace storage on the same host/storage system;
- one or more isolated worker processes/containers;
- local preview routing.

Subject to security design, the first version does **not** require:

- Kubernetes;
- a distributed task queue;
- Redis solely for orchestration;
- Kafka/event streaming infrastructure;
- separate microservices for every logical component;
- distributed locking infrastructure;
- horizontal worker autoscaling.

However, even when co-located, implementation must preserve logical boundaries:

- long-running engine work is not executed inside a normal request handler;
- control state is durable;
- worker failure does not destroy the workspace;
- execution ownership is explicit;
- adapter-specific code does not leak into unrelated product modules.

---

# 44. Evolution Toward Multiple Hosts

This document does not need scale-out, but the state model should not prevent it.

If Kallula later runs coordinators/workers on multiple hosts, the following architectural concepts already provide the necessary foundation:

- durable commands;
- exclusive Project execution lease;
- Execution Attempt identity;
- heartbeat/liveness;
- durable canonical workspace accessible to the selected worker;
- idempotent command/event processing;
- reconciliation;
- immutable Run configuration.

The physical implementation can evolve without changing the Product/Run semantics.

---

# 45. Backup and Restore Architecture

A consistent Kallula backup must eventually include:

1. durable control-plane state;
2. Project workspaces/Git repositories;
3. protected credential material and the external key-management information required to decrypt it;
4. configuration required to locate/interpret backed-up workspaces;
5. supported engine/adapter metadata needed to interpret historical Runs.

Disposable Execution Workers do not need backup.

## 45.1 Restore principle

Restore must not create a situation where control state claims a Run is actively executing when its worker no longer exists.

After restore, all non-terminal Runs should go through reconciliation before new execution begins.

---

# 46. Observability Architecture

There are three observability layers.

## 46.1 Product activity

User-understandable normalized events:

- stage started/completed;
- work item started/completed/blocked;
- tests started/completed;
- question asked/answered;
- stop requested/stopped;
- run failed/completed;
- verification outcome.

## 46.2 Execution diagnostics

Operational information such as:

- worker ID;
- attempt ID;
- process exit reason;
- lease/heartbeat state;
- adapter errors;
- model/provider diagnostics;
- preview process failures.

## 46.3 Platform telemetry

Metrics/logs/traces for Kallula itself:

- API errors/latency;
- coordinator backlog;
- stuck/expired leases;
- worker launch failures;
- reconciliation outcomes;
- storage failures;
- event-ingestion failures.

These layers should be correlated through stable Project/Run/Attempt IDs without placing secrets in telemetry.

---

# 47. Auditability

Audit records answer **who requested what product-level action**, while events answer **what happened during execution**.

The two may overlap but should not be conflated.

Audit-worthy actions include:

- creating/deleting Project;
- starting Run;
- answering interaction;
- requesting stop/resume;
- changing project defaults;
- creating/replacing/deleting credential metadata/value;
- changing credential assignment;
- modifying Agent Profile;
- changing default engine installation;
- initiating GitHub publish;
- privileged recovery/admin action.

Sensitive credential values and unnecessary model/source content must not be copied into audit records.

---

# 48. Consistency Model

Kallula is intentionally not designed as if every subsystem participates in one global transaction.

The consistency model is:

- **strong/transactional inside Kallula control-state operations where feasible;**
- **single-writer serialized mutation for each canonical Project workspace;**
- **eventual reconciliation between workspace/engine effects and control-plane projections after failures;**
- **idempotent command/event handling to make retries safe;**
- **explicit user-visible uncertainty/failure instead of invented success.**

This is sufficient for correctness without introducing a distributed transaction coordinator.

---

# 49. Important Invariants

The implementation must preserve all of the following.

### Invariant A — Workspace uniqueness

A Project has one canonical writable workspace identity.

### Invariant B — Single autonomous writer

No two active Execution Attempts may mutate the same canonical workspace concurrently in v1.

### Invariant C — Run immutability

A Run's effective engine/configuration snapshot does not change after execution begins.

### Invariant D — Attempt traceability

Every worker lifetime belongs to exactly one Execution Attempt and Run.

### Invariant E — Interaction durability

A pending human question exists durably outside the worker/browser.

### Invariant F — Stop truthfulness

`STOPPED` requires engine/adapter-confirmed safe-stop semantics, not merely process disappearance.

### Invariant G — Completion truthfulness

`COMPLETED` requires a translated terminal result, not merely exit status or lost connectivity.

### Invariant H — Verification identity

Verified State points to exact source/evidence identity.

### Invariant I — Engine isolation

Only adapter code knows native phase numbers, stop files, checkpoint formats, and artifact names.

### Invariant J — Resume safety

A resume cannot proceed until workspace and pinned engine/adapter compatibility are established.

### Invariant K — Secret isolation

Autonomous workers do not inherit Kallula host/control-plane secrets by default.

### Invariant L — Rebuildable UI state

Loss of a browser session/live stream does not lose authoritative Run history or pending interactions.

---

# 50. Architectural Decisions Resolved by This Document

The following previously-open questions are now resolved at the architectural level.

## 50.1 Resume vs new Run

Resolved: resume continues the same Run with a new Execution Attempt when objective/configuration/checkpoint remain compatible. New objectives/configurations create new Runs.

## 50.2 Worker lifecycle

Resolved: workers are disposable attempt runtimes; Run and Project state are durable and independent.

## 50.3 Single-writer semantics

Resolved: one active autonomous write lease per Project workspace.

## 50.4 Crash recovery

Resolved: expired/lost execution ownership triggers reconciliation. Process loss never directly implies success or safe stop.

## 50.5 Event ordering

Resolved: durable ingestion assigns Run-local append sequence; timestamps are metadata, not sole ordering authority.

## 50.6 Delivery semantics

Resolved: commands/events may be processed at least once; effects must be idempotent. Exactly-once infrastructure is not required.

## 50.7 Engine upgrades

Resolved: engine installations are explicit/versioned, Runs are pinned, upgrades apply to new Runs by default, and stopped Runs migrate only through validated compatibility.

## 50.8 Stage evolution

Resolved: stage topology is normalized data/capability metadata, not hard-coded phase numbers in UI/domain state.

## 50.9 Artifact evolution

Resolved: normalized Artifact records map to engine-native references; filename changes remain adapter concerns.

## 50.10 Initial topology

Resolved: single-node/co-located deployment is acceptable; microservices/distributed queueing are not required to begin.

---

# 51. Questions Deliberately Not Resolved Here

The following remain for dedicated design documents.

## 51.1 Siesta Engine Adaptation Specification

**Status: RESOLVED BY NORMATIVE SUPPORTING SPECIFICATION.**

Document: [`Kallula — Siesta Engine Adaptation Specification.md`](./Kallula%20%E2%80%94%20Siesta%20Engine%20Adaptation%20Specification.md)

That specification now defines:

- the adapter execution/programming boundary;
- the minimal generic Siesta integration seams;
- canonical external workspace injection;
- cooperative durable Phase 0 interactions and restartable pending questions;
- structured engine-event emission;
- structured engine outcomes;
- safe-stop translation;
- native state inspection and resume compatibility;
- baseline stage/work-item/artifact mappings;
- capability-manifest requirements;
- Planner/Worker/Consultant Agent Slot mapping;
- Run-scoped mutable skills/global learning context;
- Pi child-environment filtering requirements;
- launch/state-format/resume compatibility distinctions;
- compatibility-suite and upstream pin/patch/rebase strategy.

Physical worker transport, storage, sandboxing, concrete runtime secret transport, and final API/database schemas remain owned by the later specifications below.


## 51.2 Security & Credentials Design

**Status: RESOLVED BY NORMATIVE SUPPORTING SPECIFICATION.**

Document: [`Kallula — Security & Credentials Design.md`](./Kallula%20%E2%80%94%20Security%20%26%20Credentials%20Design.md)

That specification now defines:

- the threat model and trust classification;
- server-managed browser sessions, CSRF/origin constraints, and authorization principles;
- credential security domains and plaintext/non-plaintext boundaries;
- envelope encryption and root/KEK separation;
- credential creation/replacement/assignment/revocation/deletion semantics;
- worker and Pi environment allowlists;
- model-provider credential policy;
- Project runtime secret injection boundaries;
- GitHub App/trusted-integration authentication;
- Preview origin/cookie/network isolation;
- repository/path/symlink security constraints;
- redaction and secret-scanning policy;
- audit and compromise-response requirements;
- security compatibility tests.

Concrete KMS/KeyProvider, worker sandbox, network-policy implementation, Preview routing technology, and runtime secret transport remain owned by later implementation designs.


## 51.3 Execution Environment & Preview Design

**Status: RESOLVED BY NORMATIVE SUPPORTING SPECIFICATION.**

Document: [`Kallula — Execution Environment & Preview Design.md`](./Kallula%20%E2%80%94%20Execution%20Environment%20%26%20Preview%20Design.md)

That specification now defines:

- hosted OCI-compatible worker/Preview isolation and development-only process mode;
- Runtime Manager privilege boundary;
- durable canonical Workspace and Run Engine Runtime physical roles;
- immutable Engine Installation and pinned Environment Snapshot attachment;
- curated runtime packs and dependency/build execution boundaries;
- worker mounts, resource limits, Attempt lifecycle, heartbeat, safe-stop/resume, and runtime failure classification;
- execution and Preview network zones;
- Runtime Plan, service discovery/configuration, ports, dependencies, and supporting services;
- separate Preview build/application-runtime phases;
- immutable committed Preview source snapshots;
- Preview Instance lifecycle, Gateway routing, separate origin, scoped access, health, logs, cleanup, and crash reconciliation;
- service-scoped runtime credential injection;
- initial single-host implementation and future multi-host driver boundary.

Exact runtime vendor, filesystem/storage backend, firewall implementation, Preview proxy product, runtime-pack catalog, and log backend remain implementation selections rather than architectural questions.


## 51.4 API & Data Contract Specification

**Status: RESOLVED BY NORMATIVE SUPPORTING SPECIFICATION.**

Document: [`Kallula — API & Data Contract Specification.md`](./Kallula%20%E2%80%94%20API%20%26%20Data%20Contract%20Specification.md)

That specification now defines:

- stable resource identities and JSON conventions;
- logical persistence entities, fields, relationships, and correctness constraints;
- Run, Attempt, lease, Command, Interaction, Work Item, Event, Artifact, Verification, Verified State, Engine, Environment, Runtime Plan, Credential, Integration, and Preview representations;
- immutable versus mutable resource behavior;
- versioned `/api/v1` HTTP contracts;
- ETags/optimistic concurrency;
- request idempotency;
- durable command semantics;
- per-Run Event sequence, adapter-event deduplication, replay, and SSE live delivery;
- account-level invalidation stream;
- pagination/cursors;
- standard problem/error responses;
- transaction boundaries;
- security-sensitive write-only and never-returned data;
- API/schema evolution rules.

Framework, relational database product, ORM, queue/wakeup mechanism, SSE implementation, and physical indexing remain implementation selections.


## 51.5 UX & Interaction Specification

**Status: RESOLVED BY NORMATIVE SUPPORTING SPECIFICATION.**

Document: [`Kallula — UX & Interaction Specification.md`](./Kallula%20%E2%80%94%20UX%20%26%20Interaction%20Specification.md)

That specification now defines:

- global and Project navigation;
- Dashboard attention ordering;
- Project creation/import flows;
- durable typed pending-interaction UX;
- Run, Stage, Work Item, and Execution Attempt presentation;
- safe-stop and resume affordances;
- failure, compatibility, and reconciliation presentation;
- current workspace versus Verified State trust indicators;
- Activity, test evidence, Files, Git, Preview, and Runtime Logs;
- Agent, Environment, Credential, Knowledge, History, and Engine/System surfaces;
- capability-driven control rendering;
- stale/reconnect/empty/partial states;
- mobile priorities and accessibility behavior.

Security mechanics, exact Environment/runtime controls, GitHub authorization, and final visual design system remain owned by later specifications.

---

# 52. Implementation Sequencing Implications

This architecture suggests implementation should proceed through thin vertical slices rather than building all infrastructure first.

The first architectural proof should validate:

```text
Browser request
    ↓
Durable Project + Run creation
    ↓
Run Coordinator claims Run
    ↓
Single Project lease acquired
    ↓
Siesta adapter starts pinned engine against durable workspace
    ↓
Siesta requests one human answer
    ↓
Pending Interaction persisted
    ↓
Browser answers after reconnect
    ↓
Execution resumes
    ↓
Normalized event visible
```

A second proof should validate:

```text
Run executing
    ↓
Safe stop requested
    ↓
Engine confirms supported boundary
    ↓
Worker ends
    ↓
Run STOPPED
    ↓
New Execution Attempt resumes same Run/workspace
```

A third proof should validate:

```text
Worker dies unexpectedly
    ↓
Lease becomes uncertain/expired
    ↓
Reconciler inspects workspace/checkpoint
    ↓
Run becomes truthful FAILED/resumable state
    ↓
Explicit recovery starts new Attempt
```

Only after these seams are proven should broader UI, GitHub publishing, sophisticated previewing, notifications, or scale-out receive significant implementation effort.

---

# 53. Architectural Acceptance Criteria

This document is considered successfully implemented when the system can demonstrate the following behaviors.

## AC-ARCH-001 — Browser disconnect

An active Run continues after the browser disconnects, and reconnect reconstructs state from durable backend records.

## AC-ARCH-002 — Durable interaction

A Siesta question survives browser/control-plane restart and can be answered exactly once.

## AC-ARCH-003 — Single writer

Concurrent start/resume requests cannot produce two active workers modifying the same Project workspace.

## AC-ARCH-004 — Attempt history

A worker restart/resume produces a new Execution Attempt without losing the identity/history of the logical Run.

## AC-ARCH-005 — Crash truthfulness

Killing the active worker does not cause the Run to become `COMPLETED` or `STOPPED` automatically.

## AC-ARCH-006 — Safe stop truthfulness

`STOP_REQUESTED` persists until the engine confirms the supported boundary; then and only then does the Run become `STOPPED`.

## AC-ARCH-007 — Resume compatibility

A Run whose checkpoint cannot be proven compatible does not restart automatically.

## AC-ARCH-008 — Canonical workspace

Source browsing, Git view, engine execution, verification, export, and resume all refer to the same canonical Project workspace/source identity.

## AC-ARCH-009 — Verified/current distinction

After new unverified modifications, Kallula still identifies the older exact Verified State separately from the current workspace.

## AC-ARCH-010 — Engine pinning

Changing the default Siesta revision affects new Runs but does not silently alter an existing active/stopped Run's engine identity.

## AC-ARCH-011 — Adapter containment

No frontend or general Project/Run service needs to know that current Siesta uses `phase-0`, `stop.md`, `.pipeline-checkpoint`, `spec.md`, `issues.md`, or Planner/Worker/Consultant native names.

## AC-ARCH-012 — Event replay

After a live-update connection is interrupted, the client can retrieve events after its last durable Run-local sequence and reconstruct activity without gaps caused solely by the connection loss.

## AC-ARCH-013 — Command idempotency

Retrying start/answer/stop/resume requests due to network uncertainty does not duplicate their execution effects.

## AC-ARCH-014 — Control-plane restart

Restarting the Control Plane/Coordinator does not delete Project/Run state and triggers reconciliation of non-terminal Runs.

## AC-ARCH-015 — Worker secret boundary

Inspection of a normal autonomous worker environment confirms it does not automatically contain Kallula platform/database/GitHub/host credentials.

---

# 54. PRD Traceability

This architecture directly operationalizes the following major PRD areas:

| PRD area | Architectural resolution in this document |
|---|---|
| §6 foundational principles | §§3–4, 49 |
| §7 product ownership boundaries | §§7–8 |
| §8 engine evolution contract | §§35–39 |
| §9 core domain model | §§9–12, 15–17, 23, 25–26 |
| §10 product state model | §§13–17 |
| KAL-FR-040–046 interactions | §§17, 28 |
| KAL-FR-050–053 execution | §§11–14, 21, 27 |
| KAL-FR-060–073 monitoring/events | §§22, 41, 46 |
| KAL-FR-080–083 safe stop | §§18, 29 |
| KAL-FR-090–093 resume | §§19, 30, 33 |
| KAL-FR-100–102 failure | §§32–33 |
| KAL-FR-110–123 work/test evidence | §§16, 22–25 |
| KAL-FR-130–164 files/Git/integration | §§8, 24, 42 |
| KAL-FR-170–182 preview/logs | §§26, 42 |
| KAL-FR-190–224 environment/agents/skills | §§35–39 |
| KAL-FR-230–243 credentials/isolation | §§7.11, 42 |
| KAL-FR-250–281 knowledge/provenance/history | §§8, 22–25, 47 |
| §16 control-plane responsibilities | §§6–7 |
| §17 engine adapter requirements | §§7.6, 35–39 |
| §18 backend flows | §§27–31 |
| §19 persistence/source-of-truth | §§8, 20–24, 40, 48 |
| §20 reproducibility | §§11.2, 35–39 |
| §21 security | §42 |
| §22 reliability/recovery | §§20–21, 32–33 |
| §23 maintainability/upstream compatibility | §§35–39 |
| §24 observability/auditability | §§22, 46–47 |
| §25 scalability | §§43–44 |
| §29 acceptance criteria | §§49, 53 |

---


# 55. Implementation Status

The implementation plan now exists:

> [`Kallula — Implementation Plan.md`](./Kallula%20%E2%80%94%20Implementation%20Plan.md)

Use that document to sequence development and select the first-release implementation choices.

No more architecture document is required before coding starts.

The **Test & Compatibility Strategy** is still required before release. It is intentionally deferred until the implementation has real testable seams, runtime behavior, and compatibility fixtures.


# Appendix A — State Transition Table

| Current Run state | Trigger | Preconditions | Next state | Notes |
|---|---|---|---|---|
| `QUEUED` | coordinator claims execution | Project lease available | `STARTING` | creates new Attempt |
| `STARTING` | engine confirms active | launch successful | `RUNNING` | stage tracked separately |
| `STARTING` | launch fails | no safe auto-retry remaining | `FAILED` | evidence retained |
| `RUNNING` | engine asks human | interaction durably stored | `WAITING_FOR_HUMAN` | browser may be absent |
| `WAITING_FOR_HUMAN` | answer accepted | interaction PENDING | `RUNNING` or `QUEUED` | adapter-dependent; current Siesta adaptation uses `QUEUED` and a new Attempt after cooperative suspension |
| `RUNNING` | safe stop accepted | command persisted | `STOP_REQUESTED` | no claim of stop yet |
| `WAITING_FOR_HUMAN` | safe stop accepted | command persisted | `STOP_REQUESTED` | interaction may close/carry per adapter semantics |
| `STOP_REQUESTED` | engine confirms safe boundary | evidence/checkpoint recorded | `STOPPED` | release lease |
| `STOP_REQUESTED` | execution fails before confirmation | reconciliation done | `FAILED` | never infer STOPPED |
| `RUNNING` | engine terminal success/result | translated terminal evidence persisted | `COMPLETED` | may create Verified State |
| `RUNNING` | engine terminal failure | failure persisted | `FAILED` | recovery metadata recorded |
| `STOPPED` | explicit resume | compatibility + no lease | `QUEUED` | same Run, new Attempt |
| `FAILED` | explicit recovery | recoverable + compatible | `QUEUED` | same Run, new Attempt |
| `COMPLETED` | new requested work | n/a | **new Run** | no transition of completed Run |

---

# Appendix B — Source-of-Truth Decision Rules

1. **Who owns the fact?** Use that system first.
2. **Can the fact be derived?** Prefer recomputation over creating a second editable authority.
3. **Is the workspace newer than the projection?** Reconcile; do not overwrite source from projection.
4. **Is control state newer than engine evidence?** Determine whether the command was accepted but not yet executed; do not fake engine completion.
5. **Is liveness uncertain?** Mark the Attempt uncertain/lost and reconcile before granting a new write lease.
6. **Does verification evidence disagree with narrative?** Mechanical evidence wins.
7. **Does the pinned engine disagree with the current default engine?** The pinned Run identity wins.

---

# Appendix C — Architectural Vocabulary

**Control Plane** — Kallula's product-facing application boundary that owns Project/Run/configuration/interaction/integration state. **Run Coordinator** — The component that converts durable asynchronous commands into worker/adapter actions. **Reconciler** — The responsibility that resolves uncertain/stale execution state after failures/restarts. **Execution Attempt** — One concrete worker lifetime/ownership period under a logical Run. **Project execution lease** — Exclusive autonomous write ownership of the canonical Project workspace. **Canonical workspace** — The authoritative filesystem/Git state for a Project. **Engine Installation** — A tested engine revision + compatible adapter + capability identity available to Kallula. **Engine Adapter** — The anti-corruption layer translating stable Kallula concepts to/from Siesta-native behavior. **Normalized event** — Durable Kallula event representing a meaningful product/execution occurrence. **Artifact Index** — Metadata mapping normalized artifact concepts to authoritative native evidence/content. **Verified State** — An exact Project source state backed by successful verification evidence. **Pending Interaction** — A durable request for human input that exists independently of browser or worker lifetime. **Capability manifest** — Versioned description of behaviors/configuration exposed by a particular Engine Installation.

---

# Final Architectural Rule

> **Kallula must lose a browser, web process, coordinator process, or worker process without losing the distinction between user intent, current project state, engine checkpoint state, and verified state. Siesta-specific mechanics must remain behind the adapter boundary, and no infrastructure abstraction should be introduced merely because future scale might need it.**
