# Kallula — Product Requirements Document

**Document status:** Foundational Product Requirements, refined from the initial *Siesta Cloud* PRD
**Product name:** Kallula
**Engine:** Siesta (upstream project: `jairorodriguezarias/siesta`)
**Repository baseline reviewed:** `main`, tree/commit snapshot `20b149e0734b09730dfd22803d2695776fcf84b8`
**Implementation status:** Tracked by the [Implementation Plan](./Kallula%20%E2%80%94%20Implementation%20Plan.md)
**Purpose:** Primary product specification for product design, architecture, UX design, and implementation planning
**Audience:** Product, frontend, backend/control-plane, engine-integration, security, infrastructure, and QA engineers
**Normative supporting architecture:** [`Kallula — System Architecture & State Model.md`](./Kallula%20%E2%80%94%20System%20Architecture%20%26%20State%20Model.md)
**Normative Siesta integration specification:** [`Kallula — Siesta Engine Adaptation Specification.md`](./Kallula%20%E2%80%94%20Siesta%20Engine%20Adaptation%20Specification.md)
**Normative UX & interaction specification:** [`Kallula — UX & Interaction Specification.md`](./Kallula%20%E2%80%94%20UX%20%26%20Interaction%20Specification.md)
**Normative security & credentials design:** [`Kallula — Security & Credentials Design.md`](./Kallula%20%E2%80%94%20Security%20%26%20Credentials%20Design.md)
**Normative execution environment & Preview design:** [`Kallula — Execution Environment & Preview Design.md`](./Kallula%20%E2%80%94%20Execution%20Environment%20%26%20Preview%20Design.md)
**Normative API & data contract specification:** [`Kallula — API & Data Contract Specification.md`](./Kallula%20%E2%80%94%20API%20%26%20Data%20Contract%20Specification.md)

> **Interpretation rule:** This PRD defines required product behavior, boundaries, invariants, flows, and acceptance criteria. It deliberately does **not** authorize premature implementation of unresolved architectural mechanisms. Where correctness depends on a deeper design decision, the requirement is fixed and the mechanism remains open until a supporting design document resolves it.

> **Document precedence:** The PRD remains authoritative for product requirements and invariants. The **System Architecture & State Model** is authoritative for system boundaries, state ownership, Run/Execution Attempt lifecycle, execution leases, persistence semantics, crash reconciliation, resume semantics, and engine-version pinning. The **Siesta Engine Adaptation Specification** is authoritative for the current Siesta-specific engine boundary and compatibility contract. The **UX & Interaction Specification** is authoritative for browser information architecture and interaction semantics. The **Security & Credentials Design** is authoritative for authentication/session requirements, trust-domain enforcement, credential classes, encryption/key hierarchy, secret exposure, GitHub/provider authority, Preview security constraints, redaction, auditability, and compromise response. The **Execution Environment & Preview Design** is authoritative for hosted workload isolation, canonical workspace attachment, Run Engine Runtime persistence, Environment Snapshots/runtime packs, resource/network policy, generated application services, runtime-only secret injection, immutable Preview source snapshots, Preview gateway/origin/access behavior, runtime logs, cleanup, and runtime crash reconciliation. The **API & Data Contract Specification** is authoritative for stable resource schemas, logical persistence entities/constraints, HTTP endpoints, durable-command semantics, optimistic concurrency, idempotency, normalized Event payloads, pagination, errors, SSE replay/live-update behavior, and fields that may or may not cross the browser boundary. Within their scopes, higher-level product/architecture invariants constrain all supporting specifications. Conflicts must be reconciled deliberately rather than resolved implicitly in code.

---

# 1. Executive Summary

Kallula is a browser-based control plane for autonomous software development.

Its first execution engine is the open-source **Siesta** software factory. Siesta remains responsible for the autonomous software-development workflow: clarifying intent, producing a specification, planning issues, implementing them with coding agents, consulting when needed, reviewing code, mechanically verifying the result, recording knowledge, and learning from execution.

Kallula is responsible for turning that engine into a persistent product that a user can operate remotely and safely.

A user should create a software project, answer requirements questions in the browser, select or configure agent behavior, start a run, close the browser, return later from another device, understand exactly what happened, inspect the source/test/Git evidence, safely stop or resume execution, preview a runnable application, and retrieve or publish the generated project without direct access to the host machine.

The defining architectural principle is:

> **Kallula must depend on stable engine capabilities and normalized product contracts, not on Siesta's current filenames, role names, phase numbers, terminal behavior, or internal implementation details.**

Siesta is expected to evolve. The Kallula UI, project model, event history, run history, credentials subsystem, Git integration, preview system, and user-facing APIs must remain stable when practical even if Siesta changes its internal pipeline.

Kallula initially supports **one engine: Siesta**. This PRD does not need a marketplace of interchangeable engines. However, the Siesta integration must be treated as an explicit adapter boundary so normal upstream evolution does not force changes throughout the rest of Kallula.

---

# 2. Product Definition

```text
Idea / Repository
       |
       v
+------------------+
| Clarify intent   |
+------------------+
       |
       v
+------------------+
| Plan the work    |
+------------------+
       |
       v
+------------------+
| Build + review   |
+------------------+
       |
       v
+------------------+
| Verify           |
+------------------+
       |
       v
 Preview / Source / Publish
```


Kallula is not merely “Siesta on a remote server.”

Kallula is:

> **A persistent, inspectable, configurable, browser-operated software factory in which autonomous execution can continue without a browser session while project state, Git history, verification evidence, human decisions, engine configuration, and execution provenance remain durable and understandable.**

The expected high-level experience is:

```text
Create Project
    ↓
Describe the goal
    ↓
Clarify requirements
    ↓
Confirm intent
    ↓
Generate specification
    ↓
Generate implementation plan
    ↓
Autonomous implementation
    ↓
Tests / commits / consultations / recovery
    ↓
Review
    ↓
Verification
    ↓
Inspect preview and evidence
    ↓
Download or publish source
    ↓
Continue the project in later runs
```

Normal product use must not require SSH, direct VM access, Docker commands, SCP, terminal interaction with Siesta, or manual copying of runtime files.

---

# 3. Why Kallula Exists

Siesta already provides important software-factory behavior. The current upstream implementation is intentionally local and pipeline-centric. It currently:

- runs as a Python orchestrator;
- invokes Pi as the coding-agent runtime;
- uses Planner, Worker, and Consultant routes;
- performs a terminal-mediated Phase 0 interview;
- writes generated projects to a filesystem workspace;
- uses Git as part of execution and recovery;
- persists pipeline progress in project-local files;
- stops at issue boundaries using `stop.md`;
- maintains project and global knowledge graphs;
- mechanically gates issue completion, review, and verification;
- can modify selected factory skills through its learner;
- inherits the current process environment when invoking Pi, augmented with `PYTHONPATH`;
- assumes one local process is writing a given KB graph at a time.

Those behaviors are valuable engine semantics, but most of them are **not appropriate as Kallula's public product contract**.

Kallula therefore adds five things around Siesta:

1. **Product state** — projects, runs, users, profiles, credentials, integrations, notifications, and durable activity history.
2. **Execution control** — start, wait for human input, stop safely, resume, recover, and report failures independently of browser connections.
3. **Normalization** — map Siesta-native phases, artifacts, events, and configuration into stable Kallula concepts.
4. **Safe infrastructure** — isolated workers, durable workspaces, secret boundaries, previews, and trusted integrations.
5. **User experience** — a responsive browser interface for creating, observing, configuring, inspecting, and retrieving projects.

---

# 4. Product Goals

## 4.1 Primary goals

Kallula must:

1. Make the existing Siesta workflow usable from a browser.
2. Preserve Siesta's mechanical reliability gates rather than replacing them with UI assumptions.
3. Allow execution to continue independently of the browser session.
4. Persist project and run state across web-process, runner, worker, and host restarts when recovery is technically possible.
5. Make autonomous work observable instead of opaque.
6. Let users configure supported agent behavior through the UI without exposing engine-breaking protocol details by default.
7. Represent a project's execution environment explicitly.
8. Securely manage integrations and project credentials without requiring server access.
9. Keep the canonical generated source and Git history available to the user.
10. Allow runnable web applications to be previewed when supported.
11. Clearly distinguish live workspace state, run state, and last verified state.
12. Preserve enough provenance to explain what the system understood, planned, changed, tested, reviewed, and verified.
13. Support safe stop and resume using the engine's real checkpoint/recovery semantics.
14. Minimize unnecessary divergence from upstream Siesta.
15. Make normal Siesta upgrades local to the engine-integration boundary where possible.
16. Pin enough engine/configuration information to explain historical runs.
17. Provide a foundation for later controlled human steering without turning the engine into an unstructured chat session.

## 4.2 Product-quality goals

The initial product should optimize for:

- correctness;
- transparency;
- recoverability;
- source ownership;
- maintainability;
- safe defaults;
- understandable state;
- a low-complexity initial deployment.

It should not optimize prematurely for hypothetical enterprise scale.

---

# 5. Non-Goals

The foundational version is not intended to be:

- a replacement for GitHub;
- a full browser IDE;
- a Kubernetes control plane;
- a generic drag-and-drop agent workflow builder;
- a real-time collaborative editor;
- an unrestricted chat shell around a coding agent;
- a system where arbitrary orchestration/system prompts can be edited casually;
- an enterprise multi-tenant platform in the first release;
- a billing platform;
- a production deployment platform for arbitrary generated applications;
- a generic secrets broker for autonomous tools;
- a multi-engine marketplace.

The design must avoid abstractions that exist only because they might become useful at very large scale.

---

# 6. Foundational Product Principles

## 6.1 Browser-first operation

After deployment, all ordinary Kallula product operations must be possible from the browser.

## 6.2 Siesta is the initial engine, not the Kallula domain model

Kallula must integrate Siesta deeply enough to preserve its strengths, but Kallula's product concepts must not be defined solely by Siesta's current implementation.

Examples:

- Kallula has a **Run**, not a “`python -m pipeline` process.”
- Kallula has **engine stages**, not hard-coded “Phase 0–7” assumptions throughout the UI.
- Kallula has **agent slots/configuration capabilities**, not product tables permanently restricted to exactly Planner/Worker/Consultant.
- Kallula has **artifacts**, not business logic that assumes `spec.md`, `issues.md`, and `verify_verdict.txt` will always be named exactly that.
- Kallula has a **safe-stop operation**, not UI logic that creates `stop.md` directly.

## 6.3 One authoritative project workspace

Each project has one canonical durable workspace representing the actual generated software project.

The code browser, Git view, preview system, source export, verification evidence, and publishing flow must derive from that authoritative state.

Kallula must not maintain competing unsynchronized copies of generated source in the control-plane database.

## 6.4 Git remains first-class

Git is part of the execution and recovery model, not an optional reporting feature.

## 6.5 Mechanical evidence outranks model narration

A model saying “tests pass” cannot substitute for Kallula/Siesta evidence that tests actually ran successfully.

A model saying “verified” cannot override a failed mechanical verification gate.

## 6.6 Autonomous execution must be inspectable

The user must see meaningful state: current stage, active work item, recent events, tests, commits, consultations, blockers, review, verification, preview, and failures.

## 6.7 Human interaction has explicit semantics

Kallula must avoid uncontrolled live instruction injection into a running worker.

Human operations must have defined semantics such as:

- answer a pending question;
- request safe stop;
- resume;
- add guidance at a supported boundary;
- retry/restart a work item;
- change a requirement through replanning;
- resolve a blocker.

## 6.8 Configuration is versioned and reproducible

A historical run must remain attributable to the configuration it actually used.

## 6.9 Secrets are not part of the default agent context

Platform and user credentials must not automatically become environment variables or prompt content visible to autonomous coding agents.

## 6.10 Capability-driven product behavior

The UI and control plane must obtain supported engine capabilities from the engine integration rather than assuming every action or stage always exists.

If the active Siesta version does not support a capability, Kallula must disable or omit the associated product action rather than pretending it is supported.

## 6.11 Raw engine evidence is retained alongside normalized state

Kallula should normalize engine behavior for product use, but must preserve enough raw engine output/artifact references to diagnose adapter mistakes and upstream changes.

## 6.12 Engine upgrades are explicit

Active and historical runs must not silently switch to a different Siesta version or materially different engine configuration midway through execution.

---

# 7. Product Ownership Boundaries

Kallula must explicitly distinguish three ownership layers.

## 7.1 Kallula-owned concepts

Kallula owns the stable product contract for:

- users/authentication;
- projects;
- runs;
- run control state;
- engine installation metadata;
- engine adapter metadata;
- normalized stages and events;
- configuration profiles and snapshots;
- credential metadata;
- integrations;
- notifications;
- project access;
- previews;
- source export;
- Git publishing;
- audit records;
- UI/API semantics.

## 7.2 Engine-owned concepts

Siesta initially owns:

- its native pipeline ordering;
- internal prompt/protocol details;
- native checkpoints;
- issue execution semantics;
- recovery rules;
- model call protocols;
- internal learning behavior;
- native project KB representation;
- engine-specific artifacts;
- mechanical gates implemented by Siesta.

Kallula may display and normalize these concepts, but must not duplicate their logic unless a deliberate product-level invariant requires it.

## 7.3 Integration-owned concepts

The Kallula–Siesta adapter owns translation between the two layers, including:

- starting/resuming Siesta against an externally owned workspace;
- supplying normalized configuration to Siesta;
- translating browser human input into engine input;
- translating safe-stop intent into engine-native semantics;
- emitting normalized events from native Siesta behavior;
- discovering native artifacts;
- mapping native phases/stages to Kallula stage information;
- reporting engine capabilities;
- reporting compatibility and version metadata;
- sanitizing the worker environment;
- exposing health and diagnostic information.

---

# 8. Engine Evolution Contract

This section is a core requirement of Kallula.

## 8.1 Objective

When Siesta changes internally, Kallula should normally require changes in **one constrained integration surface** rather than coordinated changes to the frontend, database schema, APIs, run history, preview service, credentials system, and Git integration.

## 8.2 Initial engine support

Kallula v1 supports only Siesta.

The existence of an adapter boundary must not be used as justification to implement unnecessary multi-engine plugin infrastructure.

## 8.3 Engine identity

Every executable engine distribution known to Kallula must have an identity containing at least:

- engine family (`siesta` initially);
- engine version or source revision;
- adapter version;
- compatibility status;
- capability manifest version;
- installation/build metadata sufficient for diagnostics.

## 8.4 Run pinning

Every run must be associated with the engine identity it started with.

An active run must not silently move to a newly upgraded engine.

A resumed run should use a compatible engine/adapter combination capable of reading its checkpoint and workspace state. If compatibility cannot be established, Kallula must stop and surface the incompatibility rather than guessing.

## 8.5 Capability manifest

The Siesta adapter must expose a machine-readable set of capabilities to the Kallula control plane. The exact schema is deferred, but it must express concepts such as:

- supports interactive requirements clarification;
- supports autonomous start;
- supports safe stop;
- supports resume;
- supports structured work items;
- supports review;
- supports verification;
- supports learning;
- supports runtime smoke checks;
- supports configurable agent slots;
- supports configurable skills;
- supports existing-repository mode;
- supports preview metadata discovery;
- supports human guidance at defined boundaries;
- supports specific artifact classes.

The frontend must consume Kallula product capabilities derived from this manifest rather than maintain independent hard-coded assumptions about a specific Siesta revision.

## 8.6 Stage normalization

Kallula must represent an engine stage as data.

A normalized stage should carry:

- stable Kallula stage category where meaningful;
- engine-native stage identifier;
- display label;
- sequence/order information where meaningful;
- current state;
- optional work-item progress;
- optional parent/child relationship;
- whether user action may be required.

The UI may present familiar categories such as Requirements, Specification, Planning, Execution, Review, Verification, and Learning, but it must not require Siesta to retain exactly the current numeric phase model forever.

## 8.7 Agent-slot normalization

Kallula must not assume that there will always be exactly three configurable roles.

The adapter should expose engine-defined agent slots with metadata such as:

- stable engine slot identifier;
- label;
- purpose;
- whether it is user configurable;
- supported provider/model fields;
- supported reasoning configuration;
- supported instructions/skills configuration;
- locked protocol configuration;
- validation constraints.

For the current Siesta version, these slots map to Planner, Worker, and Consultant, with reviewer/proxy/learner usage inherited from Siesta's orchestration.

## 8.8 Artifact normalization

Kallula must maintain an artifact registry per run/project rather than requiring product code to know every native filename.

Artifact classes may include:

- intent/interview transcript;
- specification;
- plan/work-item list;
- source tree;
- test evidence;
- model-call evidence;
- review evidence;
- verification evidence;
- checkpoint;
- project knowledge;
- run learning;
- recovery bundle;
- runtime logs.

The Siesta adapter may discover current files such as `spec.md`, `issues.md`, `.pipeline-checkpoint`, `verify_verdict.txt`, KB graphs, and output logs and register them using normalized artifact classes.

## 8.9 Event normalization

The control plane must persist normalized execution events.

The adapter may produce them through native hooks added to Siesta, a structured side channel, or another deliberately designed mechanism. Parsing human-oriented console text should not be the long-term authoritative integration.

Every normalized event must retain enough native context to diagnose the original engine action.

## 8.10 Configuration normalization

Kallula must distinguish:

- **portable configuration** understood by the product;
- **engine-specific configuration** understood only by Siesta.

Engine-specific settings must be namespaced/versioned so a Siesta upgrade can change them without corrupting unrelated Kallula configuration.

## 8.11 Checkpoint opacity

Kallula must treat native Siesta checkpoint data as engine-owned.

The control plane may record checkpoint metadata and status, but it must not duplicate Siesta's checkpoint semantics in business logic.

## 8.12 Compatibility validation

Before a new Siesta version becomes the default engine for new Kallula runs, it must pass an integration compatibility suite covering at minimum:

- project creation;
- interactive interview bridge;
- autonomous mode;
- workspace routing;
- event translation;
- artifact discovery;
- successful issue execution;
- mechanical test gating;
- safe stop;
- resume;
- failed-run reporting;
- review/verification truthfulness;
- configuration mapping;
- environment isolation;
- source/Git preservation.

## 8.13 Upgrade workflow

A normal engine upgrade should conceptually be:

```text
New Siesta revision discovered/selected
    ↓
Adapter compatibility checked
    ↓
Compatibility tests executed
    ↓
Capability differences reviewed
    ↓
Adapter updated only where required
    ↓
Engine marked supported
    ↓
New runs may use it
    ↓
Existing runs remain pinned unless a compatible resume policy explicitly allows migration
```

Kallula must not auto-upgrade active runs merely because the server has a newer Siesta checkout.

---

# 9. Core Domain Model

## 9.1 User

The initial product may target one authenticated owner, but ownership must be represented explicitly enough that future multi-user support is not made impossible.

## 9.2 Project

A Project represents a software product or repository being built or maintained.

A Project persists independently of any one execution attempt.

A project contains/references:

- stable project ID;
- display name;
- original request/intent history;
- canonical workspace;
- Git repository state;
- default engine selection;
- default configuration profile;
- environment configuration;
- assigned project credentials;
- engineering preferences;
- run history;
- artifact history;
- knowledge references;
- preview configuration;
- last verified state.

## 9.3 Workspace

The Workspace is the canonical durable filesystem for the generated software project.

It must survive worker termination.

It includes engine-produced application source and engine-required project state. The exact native contents may evolve with Siesta.

## 9.4 Run

A Run is one bounded execution attempt against a project.

Examples:

- initial build;
- continuation after a stop;
- resumed execution after infrastructure interruption;
- later feature implementation;
- future maintenance request.

A Run records at minimum:

- run ID;
- project ID;
- control state;
- engine identity;
- configuration snapshot;
- start/end timestamps;
- normalized stage state;
- normalized events;
- native diagnostic references;
- pending human interaction;
- errors;
- final result;
- resource/cost data where available.

The exact distinction between “resume same run” and “create a new run continuing the same project” must be resolved in the System Architecture & State Model. The product must make the distinction visible and consistent.

## 9.5 Work Item

A Work Item is a normalized unit of planned/active/completed engine work.

For current Siesta this normally maps to an issue in `issues.md`.

A work item may contain:

- native identifier;
- title/description;
- acceptance criteria where known;
- dependencies where known;
- state;
- attempts;
- consultations;
- test evidence;
- associated commits;
- blockers.

## 9.6 Engine Installation

Represents a known Siesta revision/build and its compatibility metadata.

## 9.7 Engine Adapter

Represents the Kallula integration implementation that understands a compatible range of Siesta behavior.

## 9.8 Agent Profile

An Agent Profile is a named, versioned set of user-configurable agent settings compatible with an engine capability manifest.

## 9.9 Environment Profile

An Environment Profile describes the execution environment presented to a project/worker.

It may include:

- runtime languages and versions;
- system/build dependencies;
- services;
- resource limits;
- network policy;
- exposed application ports;
- preview capability;
- environment image/profile version.

The exact runtime technology remains a separate architecture decision.

## 9.10 Credential

A Credential is a protected secret or sensitive configuration value managed by Kallula.

Credential metadata is separate from its encrypted value.

## 9.11 Integration

An Integration is a trusted external service Kallula itself connects to, such as GitHub.

Integrations are distinct from project credentials used by generated software.

## 9.12 Event

An Event is a durable structured record of something significant that occurred.

## 9.13 Artifact

An Artifact is a discoverable piece of project/run evidence with a normalized class and native engine reference.

## 9.14 Preview

A Preview is a routed, isolated browser-accessible application process originating from the project environment.

Preview health is not equivalent to final verification.

## 9.15 Verified State

A Verified State represents the most recent project checkpoint for which required engine verification and mechanical gates successfully completed.

---

# 10. Product State Model

> **Architecture reference:** The normative lifecycle and transition semantics for Project, Run, Execution Attempt, Pending Interaction, safe stop, resume, failure recovery, and Verified State are defined in [`Kallula — System Architecture & State Model.md`](./Kallula%20%E2%80%94%20System%20Architecture%20%26%20State%20Model.md), especially §§9–19 and Appendix A. This section defines the product-visible state requirements.

## 10.1 Control state and engine stage are separate

Kallula control state must be distinct from engine-native stage.

Initial run control states should support at least:

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

Additional states may be introduced only when an actual lifecycle need requires them.

## 10.2 Stage information

The current Siesta adapter may initially normalize native phases about as:

```text
Requirements / Interview
Specification
Planning
Execution
Review
Verification
Learning
Completed
```

This mapping is display/normalization behavior, not a permanent requirement that Siesta retain its current phase numbers.

## 10.3 Progress truthfulness

Kallula must not fabricate precise percentage progress when the engine cannot support it.

Before a plan exists, categorical stage progress is appropriate.

After work items exist, progress may use known counts such as `3 / 7 work items complete`.

---

# 11. Functional Requirements

The identifiers below are intended to make later architecture, UX, API, test, and implementation documents traceable.

## 11.1 Authentication and ownership

**KAL-FR-001** — Kallula must require authentication for non-public product operations.

**KAL-FR-002** — Every project must have explicit ownership metadata even in the initial single-owner deployment.

**KAL-FR-003** — Multi-organization RBAC is not required for the first release.

## 11.2 Dashboard and project list

**KAL-FR-010** — The dashboard must show projects without requiring each project to be opened to discover state.

**KAL-FR-011** — A project summary must show whether it is running, waiting for input, stopped, failed, completed, or otherwise requires attention.

**KAL-FR-012** — The dashboard should show the last verified state or equivalent trust indicator when available.

**KAL-FR-013** — The dashboard should surface recent completion/failure/attention events.

## 11.3 Project creation from an idea

**KAL-FR-020** — A user must create a project from a natural-language request.

**KAL-FR-021** — Creation must assign a stable internal project identifier independent of display name and slug.

**KAL-FR-022** — Creating a project must allocate/reserve a durable workspace before autonomous work can modify source.

**KAL-FR-023** — Project creation must allow selection of an engine/profile/environment only to the degree those choices are supported by current capabilities.

**KAL-FR-024** — The default flow should minimize infrastructure configuration before the product understands the project.

**KAL-FR-025** — The user must choose an interactive clarification flow or supported autonomous/defaulted flow.

## 11.4 Existing repository import

**KAL-FR-030** — Kallula should support creating a project from an existing Git repository.

**KAL-FR-031** — Repository import must preserve existing Git history.

**KAL-FR-032** — Kallula should support selecting the starting branch/revision.

**KAL-FR-033** — Generated work should normally occur on a dedicated working branch rather than silently modifying the default branch.

**KAL-FR-034** — Exact branch and pull-request policy must be specified before implementation of publish-to-existing-repository flows.

## 11.5 Requirements interview / human interaction bridge

**KAL-FR-040** — When Siesta requests human input, the question must be represented as a durable Kallula interaction rather than depending on a live terminal.

**KAL-FR-041** — The user must answer pending questions from the browser.

**KAL-FR-042** — Closing the browser must not lose the pending question.

**KAL-FR-043** — While human input is required, run control state must become `WAITING_FOR_HUMAN` or an equivalent explicit state.

**KAL-FR-044** — Reopening the project must restore the pending interaction with enough context to answer correctly.

**KAL-FR-045** — The product must preserve Siesta's explicit intent confirmation semantics when using interactive mode unless the user intentionally delegated the remaining decisions.

**KAL-FR-046** — The bridge must be designed as an engine interaction capability rather than frontend code calling Siesta terminal functions directly.

## 11.6 Starting execution

**KAL-FR-050** — Starting a run must create an immutable/effectively immutable execution configuration snapshot.

**KAL-FR-051** — The snapshot must include engine identity and adapter identity.

**KAL-FR-052** — Long-running execution must occur outside normal synchronous web-request lifetimes.

**KAL-FR-053** — Browser disconnection must not stop the run.

## 11.7 Run monitoring

**KAL-FR-060** — The active run view must show control state, current engine stage, active work item where known, recent events, test state, preview state, engine/configuration summary, and last verified state.

**KAL-FR-061** — Active views should receive updates without manual page refresh.

**KAL-FR-062** — Historical events must remain available after reconnecting.

**KAL-FR-063** — Live transport technology is an implementation decision; the product contract is timely server-to-browser updates plus durable history.

## 11.8 Structured events

**KAL-FR-070** — Significant engine/control changes must produce structured normalized events.

The event model must support at minimum the semantic equivalents of:

- run queued/started/completed/failed;
- stage started/completed;
- question requested/answered;
- work item started/completed/blocked;
- consultation requested/completed;
- tests started/completed;
- recovery action;
- review started/result;
- verification started/result;
- commit created;
- safe stop requested/confirmed;
- resume initiated;
- preview state changed;
- engine/adapter warning.

**KAL-FR-071** — Events must include timestamps and relevant entity references.

**KAL-FR-072** — Events must identify their source as control-plane, adapter, or engine-derived where useful for diagnostics.

**KAL-FR-073** — Normalized events must not discard critical native evidence.

## 11.9 Safe stop

**KAL-FR-080** — A user must request a safe stop through the UI.

**KAL-FR-081** — `STOP_REQUESTED` and confirmed `STOPPED` must be visually and semantically distinct.

**KAL-FR-082** — The product must not claim a safe stop until the engine/runner confirms a supported safe boundary was reached.

**KAL-FR-083** — For current Siesta, the adapter may translate safe stop into native issue-boundary semantics such as `stop.md`, but this native mechanism must not leak into Kallula API/UI contracts.

## 11.10 Resume

**KAL-FR-090** — Stopped/interrupted execution must be resumable when the pinned engine state supports it.

**KAL-FR-091** — Resume must use the existing canonical workspace and engine checkpoint state; it must not silently recreate the project from the original prompt.

**KAL-FR-092** — Kallula must verify engine/adapter compatibility with the stored checkpoint before resume.

**KAL-FR-093** — The UI must indicate that work is being continued, not created from scratch.

## 11.11 Failure handling

**KAL-FR-100** — A failed run must expose the failed stage, active work item where applicable, reason, relevant evidence, last verified state, and available recovery actions.

**KAL-FR-101** — A worker/runtime disconnect cannot be interpreted as success merely because the frontend lost its connection.

**KAL-FR-102** — If recovery is unsafe or incompatible, Kallula must stop and explain the state rather than silently reinitialize execution.

## 11.12 Work items / issues

**KAL-FR-110** — Kallula must expose the implementation plan as normalized work items when the engine provides one.

**KAL-FR-111** — Work items should expose description, acceptance criteria, dependencies, state, attempts, consultations, tests, commits, and blockers when available.

**KAL-FR-112** — The UI must not infer “completed” solely from a model statement if mechanical completion evidence disagrees.

## 11.13 Tests and verification evidence

**KAL-FR-120** — The user must inspect current and relevant historical test evidence.

**KAL-FR-121** — The UI should show pass/fail/skip information, associated work item/stage, and verification-related runs where available.

**KAL-FR-122** — A model-authored assertion of success must be visually/semantically distinct from mechanical test success.

**KAL-FR-123** — Final verification state must be based on the engine's real verification outcome and required Kallula-level gates, not presentation logic.

## 11.14 Files/source access

**KAL-FR-130** — The user must browse the actual canonical project source.

**KAL-FR-131** — The source view must provide directory navigation and readable file content.

**KAL-FR-132** — During active autonomous execution, source should initially be read-only in the product to avoid concurrent mutation ambiguity.

**KAL-FR-133** — Browser editing is deferred until explicit coordination semantics are designed.

## 11.15 Source export

**KAL-FR-140** — The user must download a clean source archive without server access.

**KAL-FR-141** — Clean export must derive from the canonical workspace, not a stale database copy.

**KAL-FR-142** — Kallula may additionally offer a diagnostic/full-workspace export including selected engine artifacts.

**KAL-FR-143** — Export behavior must clearly distinguish product source from engine runtime evidence.

## 11.16 Git view

**KAL-FR-150** — Git state must be explicit in the UI.

The view should include where available:

- current branch;
- commit history;
- working-tree status;
- work-item-associated commits;
- latest verified commit;
- remote/publish state;
- future diff inspection.

## 11.17 GitHub integration

**KAL-FR-160** — GitHub configuration must be possible through the browser.

**KAL-FR-161** — Trusted Kallula integration code, not autonomous workers, should own GitHub publishing credentials.

**KAL-FR-162** — New projects should eventually support repository creation and pushing canonical Git history.

**KAL-FR-163** — Imported repositories should support publishing a working branch and creating a pull request.

**KAL-FR-164** — Authentication design must be specified separately before implementation. A GitHub App may be appropriate but is not mandated by this PRD.

## 11.18 Application preview

**KAL-FR-170** — A runnable generated web application should be previewable without requiring the user to discover container ports.

**KAL-FR-171** — Preview state must support at least not-runnable, starting, available, unavailable, failed, and stopped.

**KAL-FR-172** — Preview may become available before final run completion.

**KAL-FR-173** — Preview success must not imply verification success.

**KAL-FR-174** — Preview must expose runtime status and relevant logs.

**KAL-FR-175** — Preview isolation/routing must receive dedicated architecture and security design.

## 11.19 Runtime logs

**KAL-FR-180** — The user must inspect application startup/runtime failures.

**KAL-FR-181** — Runtime errors should retain command/process/service context where safe.

**KAL-FR-182** — Logs must pass through secret-redaction controls before durable presentation where applicable.

## 11.20 Environment configuration

**KAL-FR-190** — Environment configuration is a first-class project capability.

**KAL-FR-191** — The default experience should support an `Auto` mode or equivalent that does not need infrastructure expertise before requirements are understood.

**KAL-FR-192** — Kallula may propose an environment after sufficient project information exists.

**KAL-FR-193** — Advanced users should inspect and, where supported, customize runtime versions, dependencies, services, network access, resources, and preview ports.

**KAL-FR-194** — The physical environment/runtime model is defined by [`Kallula — Execution Environment & Preview Design.md`](./Kallula%20%E2%80%94%20Execution%20Environment%20%26%20Preview%20Design.md); exact vendor/runtime products remain replaceable implementation choices.

## 11.21 Agent configuration

**KAL-FR-200** — The user must inspect and configure engine-exposed agent slots through the UI.

**KAL-FR-201** — For current Siesta, the UI must support the configurable Planner, Worker, and Consultant routes.

**KAL-FR-202** — Supported fields may include provider, model, reasoning/thinking level, additional behavioral/engineering instructions, and configurable skills.

**KAL-FR-203** — The UI must be generated/validated against engine-reported configuration capability rather than assuming all models/providers support identical fields.

**KAL-FR-204** — Kallula must distinguish locked engine protocol instructions from user-editable behavioral guidance.

**KAL-FR-205** — Unsupported combinations must be rejected before a run starts when validation information is available.

## 11.22 Agent profiles and versioning

**KAL-FR-210** — Agent settings should be grouped into named Agent Profiles.

**KAL-FR-211** — Effective profile changes must produce a new version/snapshot rather than silently changing historical run attribution.

**KAL-FR-212** — A project's default profile may change without retroactively changing active or historical runs.

## 11.23 Skills

**KAL-FR-220** — Kallula should expose skills assigned to configurable engine slots where the engine supports this safely.

**KAL-FR-221** — Skill content and configuration must be version-aware.

**KAL-FR-222** — Current Siesta learner modifications to factory skills must not silently invalidate historical run reproducibility.

**KAL-FR-223** — The initial hosted product should treat shared self-modifying skills conservatively; active run configuration must remain stable.

**KAL-FR-224** — A later approval/proposal workflow for learner-generated skill changes should be considered before enabling uncontrolled shared mutations.

## 11.24 Credentials

**KAL-FR-230** — Credential management must be available through the web UI.

**KAL-FR-231** — Supported actions include create/add, replace/rotate, delete, and project assignment.

**KAL-FR-232** — The UI must not offer routine secret reveal after storage.

**KAL-FR-233** — Credential values must not be stored as plaintext in normal persistent application data.

**KAL-FR-234** — Platform/integration credentials and generated-project credentials must be distinct domains.

**KAL-FR-235** — Projects must explicitly list which project credentials they are allowed to use.

**KAL-FR-236** — Secret values must remain outside generated source and run reproducibility metadata.

## 11.25 Agent credential isolation

**KAL-FR-240** — Autonomous workers must not automatically receive GitHub credentials, Kallula database credentials, SSH keys, Docker daemon access, cloud control-plane credentials, or unrelated project secrets.

**KAL-FR-241** — Current Siesta's child-process environment inheritance must be adapted for hosted Kallula execution. The worker environment must be deliberately constructed.

**KAL-FR-242** — The first release does not need to expose plaintext arbitrary project credentials to coding agents.

**KAL-FR-243** — A future trusted execution broker may inject approved secrets into specific commands without revealing values to the model, but this is explicitly deferred pending security design.

## 11.26 Knowledge

**KAL-FR-250** — Project knowledge should be inspectable through the UI.

**KAL-FR-251** — The primary knowledge view should derive from the engine's actual project knowledge/artifacts rather than creating an unsynchronized parallel store of semantic decisions.

**KAL-FR-252** — Useful normalized categories include intent, decisions, consultations, proxy decisions, blockers, work-item completion, and learning.

## 11.27 Provenance

**KAL-FR-260** — Kallula should progressively expose relationships between requirement, plan, work, evidence, and result.

A long-term provenance chain may represent:

```text
Intent
  ↓
Specification requirement
  ↓
Work item
  ↓
Agent attempt
  ↓
Consultation / decision
  ↓
Tests
  ↓
Commit
  ↓
Review
  ↓
Verification
```

Provenance is an important long-term product differentiator but need not be fully visualized in the first release.

## 11.28 Current state vs last verified state

**KAL-FR-270** — The UI must clearly separate live workspace state from the last verified project state.

**KAL-FR-271** — Intermediate source modifications must not be presented as verified output.

## 11.29 Run history

**KAL-FR-280** — Projects must expose historical runs.

**KAL-FR-281** — Historical runs retain events, engine identity, configuration snapshot, result, and artifact references.

## 11.30 Engineering preferences

**KAL-FR-290** — Projects should support persistent engineering guidance separate from functional product requirements.

Examples:

- prefer FastAPI;
- use pytest;
- target Python 3.12;
- avoid Redis unless required;
- keep domain logic out of HTTP routes.

These are factory/project preferences, not necessarily part of the generated product specification.

## 11.31 Notifications

**KAL-FR-300** — Kallula should notify the user when unattended execution requires attention or reaches a meaningful terminal state.

Candidate events include:

- human input required;
- run blocked;
- run failed;
- verification failed;
- run/project completed.

Notification channels are an implementation choice; initial support may be in-app/browser and later email.

## 11.32 Execution budgets

**KAL-FR-310** — Autonomous execution must be bounded.

Kallula should eventually support product-level limits such as:

- maximum run duration;
- maximum retries beyond engine defaults where appropriate;
- maximum model calls;
- resource limits;
- optional cost limits where measurable.

Kallula-level limits must remain distinguishable from Siesta-native retry/protocol limits.

---

# 12. Controlled Human Steering — Deferred Product Capability

The foundational release may remain autonomous after initial requirements clarification except for observation, safe stop, resume, and explicit blocker/input flows already supported by the engine.

Future steering must be state-aware.

## 12.1 Add Guidance

A user may eventually submit implementation guidance such as:

> Use server-side sessions instead of JWT authentication.

The guidance must be recorded as a human decision and applied only at a defined safe boundary.

## 12.2 Restart Current Work Item

The system may eventually allow the user to discard/archive current unverified work according to engine recovery semantics and retry the work item with new guidance.

## 12.3 Requirement Change

A functional requirement change must not be simulated as a chat message to the current worker.

A future flow should conceptually be:

```text
Pause at safe boundary
    ↓
Record requirement change
    ↓
Update specification
    ↓
Re-plan affected work
    ↓
Preserve still-valid verified work
    ↓
Resume
```

## 12.4 Human escalation policy

Future policies may include:

- fully autonomous;
- ask when blocked;
- ask for selected important decisions.

The first release does not need generalized escalation policy configuration.

---

# 13. Frontend Information Architecture

> **Normative UX reference:** Information architecture and navigation are now defined by [`Kallula — UX & Interaction Specification.md`](./Kallula%20%E2%80%94%20UX%20%26%20Interaction%20Specification.md), especially §§8–10. The structure below remains the product-level capability summary; the UX specification is authoritative for composition, navigation behavior, responsive treatment, and deep-link expectations.

All capabilities must remain reachable.

A candidate structure is:

```text
Dashboard

Projects
  └── Project
       ├── Overview
       ├── Current Run
       │    ├── Overview
       │    ├── Work Items
       │    ├── Activity
       │    └── Tests & Verification
       ├── Code
       │    ├── Files
       │    └── Git
       ├── Application
       │    ├── Preview
       │    └── Runtime Logs
       ├── Factory
       │    ├── Agents
       │    ├── Environment
       │    ├── Credentials
       │    └── Knowledge
       ├── Run History
       └── Project Settings

Settings
  ├── Agent Profiles
  ├── Credentials
  ├── Integrations
  └── Engine / System information (advanced)
```

The UI should show product concepts first and engine-native details progressively for advanced/diagnostic use.

---

# 14. Required Frontend Views

> **Normative UX reference:** The complete screen inventory, screen-level behavior, detail surfaces, and mobile priorities are defined by [`Kallula — UX & Interaction Specification.md`](./Kallula%20%E2%80%94%20UX%20%26%20Interaction%20Specification.md), especially §§15–45 and Appendix A.

## Global views

- Authentication
- Dashboard
- Project list
- Create project
- Global Agent Profiles
- Credentials
- Integrations
- Application settings

## Project views

- Project Overview
- Interview / Pending Interaction
- Current Run Overview
- Work Items
- Activity
- Tests & Verification
- Files
- Git
- Preview
- Runtime Logs
- Agents
- Environment
- Credentials
- Knowledge
- Run History
- Project Settings

## Diagnostic/advanced views

The product should make the following inspectable without making them part of the default novice workflow:

- engine version;
- adapter version;
- native engine stage ID;
- native artifact references;
- compatibility warnings;
- worker/runtime health;
- raw engine evidence/logs where safe.

---

# 15. Key Frontend Behavior

> **Normative UX reference:** Status language, capability gating, live-update freshness, Verified State presentation, responsive behavior, accessibility, and interaction microcopy are defined by [`Kallula — UX & Interaction Specification.md`](./Kallula%20%E2%80%94%20UX%20%26%20Interaction%20Specification.md), especially §§11–14 and §§41–52.

## 15.1 Responsive design

Kallula must work on desktop and mobile browsers.

Phone use must support at least:

- answering pending questions;
- observing status;
- requesting safe stop;
- resuming;
- reading failures;
- opening preview;
- receiving attention indicators/notifications.

Detailed code browsing may be more comfortable on desktop but must remain accessible.

## 15.2 Capability-driven controls

The frontend must not hard-code a button merely because a previous Siesta revision supported it.

Actions such as Resume, Retry, Preview, Add Guidance, or Skill Editing must derive from current project/run/product capabilities.

## 15.3 Trust indicators

Status must communicate evidence quality clearly.

Examples:

```text
Current workspace: changing
Last verified: commit 18fa24
Tests at last verified state: 42 passed
Current preview: available (not yet verified)
```

## 15.4 No false precision

Do not show “67% complete” unless that number has a defensible definition.

---

# 16. Backend / Control-Plane Responsibilities

> **Architecture reference:** Logical component responsibilities, execution ownership, durable command handling, reconciliation, and source-of-truth boundaries are specified normatively in [`Kallula — System Architecture & State Model.md`](./Kallula%20%E2%80%94%20System%20Architecture%20%26%20State%20Model.md), especially §§6–8 and §§20–24.

The Kallula control plane is responsible for product state, user authorization, run coordination, persistence, interactions, integrations, and normalized observability.

It is not responsible for reimplementing Siesta's internal software-development logic.

Conceptually:

```text
Browser
  │
  ▼
Kallula Web/API Control Plane
  ├── Authentication / ownership
  ├── Projects / runs
  ├── Configuration
  ├── Credentials
  ├── Interactions
  ├── Events / artifacts
  ├── Integrations
  └── Preview control
  │
  ▼
Persistent Control State
  │
  ▼
Execution Controller / Runner
  │
  ▼
Siesta Adapter
  │
  ▼
Isolated Worker Environment
  ├── Siesta engine
  ├── Pi / model tooling
  └── generated project runtime
  │
  ▼
Canonical Durable Workspace
  ├── Git
  ├── generated source
  ├── tests
  └── Siesta-native artifacts/checkpoints/KB
```

Supporting systems may include encrypted credential storage, GitHub integration, preview routing, notifications, and backup storage.

This PRD does not mandate a specific web framework, database, queue, container runtime, or reverse proxy.

---

# 17. Engine Adapter Requirements

The Siesta adapter is the most important isolation seam in Kallula.

The normative Siesta-specific integration contract is defined in [`Kallula — Siesta Engine Adaptation Specification.md`](./Kallula%20%E2%80%94%20Siesta%20Engine%20Adaptation%20Specification.md). The requirements below remain product requirements; the adaptation specification defines how the reviewed Siesta baseline satisfies them without leaking native mechanics across Kallula. The integration must support:

## 17.1 Inspect engine

- identify engine version/revision;
- identify adapter version;
- report capabilities;
- report agent slots/config schema;
- report artifact mappings;
- report compatibility with stored run state.

## 17.2 Start

- run Siesta against a Kallula-provided workspace;
- supply validated configuration;
- construct a sanitized execution environment;
- associate native execution with a Kallula run.

## 17.3 Human interaction

- publish a pending question/interaction;
- persist waiting state;
- accept an answer from Kallula;
- return the answer to Siesta without requiring a terminal.

The current Siesta `_read_answer() -> input()` behavior therefore needs a narrow adaptation seam.

## 17.4 Events

- emit normalized lifecycle events;
- retain native evidence/log references.

The exact `EventSink`-style interface is an architecture decision, not fixed here.

## 17.5 Safe stop

- receive Kallula stop intent;
- translate it to native Siesta semantics;
- confirm when a safe boundary is reached.

## 17.6 Resume

- inspect native checkpoint/workspace state;
- verify compatibility;
- continue without reconstructing product state from scratch.

## 17.7 Artifacts

- discover native artifacts;
- register normalized artifact classes;
- expose authoritative paths/references safely.

## 17.8 Environment boundary

The adapter/runner must prevent Siesta's current “inherit entire host environment” behavior from exposing Kallula platform secrets to Pi/agents.

## 17.9 Exit/result translation

A process exit code alone must not be treated as the full semantic run result.

For example, current Siesta treats a requested safe stop as a clean halt. Kallula must translate engine result semantics explicitly.

---

# 18. Canonical Backend Flows

These flows define behavior, not exact APIs.

## 18.1 New project

```text
Browser submits project request
    ↓
Control plane creates Project ID
    ↓
Durable workspace allocated
    ↓
Engine/profile/environment defaults resolved
    ↓
Run created with pinned engine + configuration snapshot
    ↓
Runner starts compatible Siesta adapter
    ↓
Siesta begins against canonical workspace
    ↓
If human input required → interaction persisted
    ↓
Run becomes WAITING_FOR_HUMAN
    ↓
Browser answers
    ↓
Adapter returns answer to Siesta
    ↓
Execution continues
```

## 18.2 Autonomous execution

```text
Intent finalized
    ↓
Siesta executes native stages
    ↓
Adapter emits normalized stage/events/artifacts
    ↓
Kallula persists control state and history
    ↓
Browser may disconnect/reconnect freely
    ↓
Final native review/verification results translated
    ↓
Kallula records completed/failed result truthfully
```

At every significant transition:

- durable control state must be updated;
- observable events should be emitted;
- browser connection must remain irrelevant to engine lifetime.

## 18.3 Safe stop

```text
User requests safe stop
    ↓
Kallula records STOP_REQUESTED
    ↓
Runner/adapter sends native stop intention
    ↓
Siesta reaches supported safe boundary
    ↓
Native checkpoint/workspace remains intact
    ↓
Adapter confirms stopped
    ↓
Kallula records STOPPED
```

## 18.4 Resume

```text
User requests resume
    ↓
Kallula loads project + run/checkpoint metadata
    ↓
Pinned/compatible engine and adapter resolved
    ↓
Canonical workspace mounted/loaded
    ↓
Adapter inspects native checkpoint
    ↓
Siesta continues
    ↓
Normalized events resume
```

## 18.5 Source download

```text
User requests clean source
    ↓
Kallula reads canonical workspace
    ↓
Export policy excludes selected runtime evidence
    ↓
Archive generated
    ↓
Browser downloads archive
```

## 18.6 GitHub publish

```text
User requests publish
    ↓
Trusted GitHub integration obtains authorization
    ↓
Canonical Git repository and target validated
    ↓
Repository/branch operation performed
    ↓
Result recorded as Kallula event/integration state
```

Autonomous workers must not require the publishing credential.

## 18.7 Preview

```text
Project runtime becomes startable
    ↓
Kallula/runner starts approved application process
    ↓
Health/availability detected
    ↓
Isolated preview route established
    ↓
Preview state becomes available
    ↓
User opens preview
```

## 18.8 Credential creation

```text
User submits secret over HTTPS
    ↓
Backend validates metadata
    ↓
Secret encrypted
    ↓
Ciphertext stored
    ↓
Metadata/assignment state retained
    ↓
Plaintext not returned through normal read APIs
```

## 18.9 Engine upgrade

```text
New supported Siesta revision introduced
    ↓
Adapter compatibility suite executed
    ↓
Capabilities/artifact mappings compared
    ↓
New engine installation marked supported
    ↓
New projects/runs may choose it
    ↓
Existing active/historical runs remain pinned
```

---

# 19. Persistence and Source-of-Truth Rules

> **Architecture reference:** The authoritative ownership matrix, conflict rules, workspace/Git semantics, Verified State identity, command durability, consistency model, and reconciliation behavior are defined in [`Kallula — System Architecture & State Model.md`](./Kallula%20%E2%80%94%20System%20Architecture%20%26%20State%20Model.md), especially §§8, 20–25, 40, and 48–49.

## 19.1 Control-plane database

Durable control-plane state should include:

- users/ownership;
- projects;
- runs;
- run control state;
- normalized stages/events;
- pending interactions;
- profile metadata and versions;
- environment metadata;
- credential metadata;
- integration state;
- engine/adapter identities;
- normalized artifact index;
- preview metadata;
- audit records.

## 19.2 Workspace

The canonical workspace remains authoritative for generated source, Git state, and engine-native project artifacts.

## 19.3 Do not duplicate engine-native semantic stores casually

Kallula may index/normalize KB and artifact information for presentation, but must avoid creating an independently editable competing source of truth unless synchronization semantics are deliberately designed.

## 19.4 Concurrency

Current Siesta's KB graph does not support concurrent writers. Kallula must respect this in initial execution design.

The product must not introduce multiple concurrent writers to the same Siesta-native project state merely because the control plane itself can handle concurrent requests.

Parallel issue execution is explicitly deferred.

---

# 20. Configuration and Reproducibility

Every run must be attributable to at least:

- project ID;
- starting Git state;
- engine family;
- Siesta version/revision;
- adapter version;
- Agent Profile version/effective snapshot;
- engine agent-slot assignments;
- provider/model identifiers;
- relevant reasoning settings;
- relevant skill versions or content hashes where practical;
- environment profile/version;
- permitted project credential **names** (never values);
- engineering preferences;
- timestamps.

Historical runs must remain explainable even after defaults change.

---

# 21. Security Requirements

> **Normative security reference:** The deployable security model and credential-flow semantics for this section are defined by [`Kallula — Security & Credentials Design.md`](./Kallula%20%E2%80%94%20Security%20%26%20Credentials%20Design.md). That document is authoritative for credential taxonomy, envelope encryption/key separation, browser sessions, worker/Pi secret boundaries, GitHub authorization, Project runtime secret injection, Preview isolation, redaction, audit, and compromise response.

## 21.1 Trust boundaries

Kallula must establish explicit isolation between:

- web/control plane;
- control-plane database;
- integration credentials;
- project credentials;
- execution controller;
- autonomous workers;
- project workspaces;
- preview applications;
- external model providers.

## 21.2 Least privilege

Workers should receive only the capabilities required for their project/run.

They should not receive by default:

- Docker socket access;
- host SSH keys;
- broad GitHub tokens;
- host filesystem access;
- Kallula DB credentials;
- cloud infrastructure credentials;
- unrelated project secrets.

## 21.3 Environment sanitization

The hosted runner must construct an allowlisted/minimal child environment rather than copying the full host environment into Siesta/Pi child processes.

Required variables must be documented by the engine adaptation/security design.

## 21.4 Credential encryption

Credential values must be encrypted at rest using a design in which the root/bootstrap decryption material is not stored as ordinary ciphertext beside the encrypted values it protects.

The initial mechanism may be operationally simple, but must have a clear migration path.

## 21.5 No routine secret reveal

Stored secrets are write/replace/delete/assign resources, not normal readable configuration values.

## 21.6 Redaction

Logs/events/artifacts displayed or persisted by Kallula must support redaction of known sensitive values and common credential patterns where appropriate.

The redaction design must explicitly address false negatives, output truncation, and native engine artifacts.

## 21.7 Preview security

Generated preview applications are untrusted project code. Preview routing must prevent them from becoming an implicit bridge into Kallula control-plane networks or other projects.

## 21.8 Model privacy

Prompts, source code, project knowledge, and run logs are private user data. Kallula should minimize unnecessary transmission to model providers and must not transmit stored secret values without an explicit product feature and security design.

---

# 22. Reliability and Recovery Requirements

**KAL-NFR-REL-001** — Browser disconnect must not stop execution.

**KAL-NFR-REL-002** — Worker termination must not delete the canonical workspace.

**KAL-NFR-REL-003** — Persistent control state must survive web/control-plane restarts.

**KAL-NFR-REL-004** — Kallula must preserve Siesta's mechanical gates: failing/absent tests, failed review, unresolved work, or failed verification cannot become successful through UI interpretation.

**KAL-NFR-REL-005** — Recoverable interrupted runs should resume from native checkpoint/Git state where compatibility is established.

**KAL-NFR-REL-006** — Failure must remain visible; Kallula must not silently discard and recreate state.

**KAL-NFR-REL-007** — Last verified state must remain available after later unverified work fails.

**KAL-NFR-REL-008** — Adapter errors must be distinguishable from engine failures where possible.

---

# 23. Maintainability and Upstream Compatibility

**KAL-NFR-MNT-001** — Kallula-specific code should remain outside upstream Siesta wherever practical.

**KAL-NFR-MNT-002** — Changes required in Siesta to support Kallula must be narrow, explicit, testable, and suitable for rebasing/reapplying against upstream changes.

**KAL-NFR-MNT-003** — Kallula business logic must not import Siesta-internal modules from arbitrary layers throughout the codebase. Engine access should pass through the adapter/integration boundary.

**KAL-NFR-MNT-004** — Siesta-native filenames, phase IDs, role names, and marker strings must not be duplicated across frontend/control-plane code.

**KAL-NFR-MNT-005** — Native-to-normalized mapping should have dedicated tests.

**KAL-NFR-MNT-006** — Every supported Siesta upgrade must be validated by an engine compatibility suite.

**KAL-NFR-MNT-007** — Kallula should record the upstream revision used by every engine installation so regressions can be reproduced.

**KAL-NFR-MNT-008** — A capability added by upstream Siesta should ideally require adapter/capability/UI enablement rather than database-wide redesign.

**KAL-NFR-MNT-009** — A capability removed/changed upstream must fail closed: Kallula must hide/disable the unsupported operation and surface compatibility information.

---

# 24. Observability and Auditability

## 24.1 Operational telemetry

Kallula should make it possible to diagnose:

- stalled runs;
- runner failures;
- adapter failures;
- engine crashes;
- failed model calls;
- timeouts;
- test failures;
- preview startup errors;
- control-plane failures;
- compatibility failures.

## 24.2 Audit records

Meaningful control actions must leave durable evidence, including:

- run started;
- configuration/engine used;
- human answers;
- safe-stop requests;
- resume requests;
- work-item completion;
- commits;
- review/verification results;
- credential metadata changes;
- Agent Profile changes;
- GitHub publish actions;
- engine default/support changes.

Secrets must not appear in audit records.

---

# 25. Performance and Scalability

**KAL-NFR-PERF-001** — Project creation/navigation must not wait synchronously for long agent work.

**KAL-NFR-PERF-002** — Active run updates should feel live under normal network conditions.

**KAL-NFR-PERF-003** — Long-running engine operations always execute outside normal request lifetimes.

**KAL-NFR-SCALE-001** — The first deployment only needs to support modest personal/small-team usage reliably.

**KAL-NFR-SCALE-002** — Do not introduce distributed queues, Kubernetes, or horizontally scaled orchestration solely for hypothetical future demand.

**KAL-NFR-SCALE-003** — Project/run identity and durable workspaces must nevertheless avoid an architectural assumption that only one project can ever exist.

---

# 26. Usability, Accessibility, and Portability

## 26.1 Usability

The default user should not need to understand container images, VM filesystem layout, internal model processes, or preview networking.

Advanced details should be available progressively.

## 26.2 Accessibility

Core state must not rely only on color.

Controls should be keyboard accessible.

Mobile layouts must remain readable.

## 26.3 Portability / source ownership

Generated source must remain retrievable independently from Kallula.

A user must not be locked into the hosted platform to access their project code.

## 26.4 Backupability

A backup design must eventually cover:

- control-plane persistent data;
- canonical project workspaces;
- engine/run metadata;
- credential-encryption restoration requirements.

Disposable worker instances do not need backup.

---

# 27. Initial Release Scope

The first usable Kallula release is successful if one user can reliably:

1. authenticate and open Kallula in a browser;
2. create a project from an idea;
3. use a selected supported Siesta engine revision;
4. choose or configure a supported Agent Profile;
5. complete Siesta's requirements clarification through the browser;
6. start autonomous execution;
7. close the browser without stopping the run;
8. return and see real control state plus normalized engine stage;
9. inspect work-item progress;
10. inspect structured activity and tests;
11. see the current workspace versus last verified state;
12. request a safe stop;
13. resume compatible stopped work;
14. browse generated source;
15. inspect Git history;
16. inspect failure/review/verification evidence;
17. preview a supported generated web application;
18. download clean project source;
19. manage credentials through the UI;
20. configure GitHub integration through the UI;
21. publish completed work to GitHub;
22. inspect/configure the project environment at an appropriate level;
23. inspect effective engine/agent configuration;
24. do all normal operations without direct VM access.

The release must also prove that Kallula can update its Siesta engine integration without requiring a rewrite of unrelated product components.

---

# 28. Explicitly Deferred Capabilities

Do not implement these until real product needs and supporting designs justify them:

- arbitrary user-created orchestration graphs;
- generic multi-engine marketplace;
- parallel multi-agent issue execution;
- unrestricted live chat with a running worker;
- arbitrary system-prompt modification;
- full browser IDE/editor;
- sophisticated secret execution broker;
- enterprise multi-tenancy and organization RBAC;
- billing;
- Kubernetes orchestration;
- distributed queueing infrastructure;
- automatic production deployment of generated applications;
- uncontrolled acceptance of self-modifying shared skills;
- generalized requirement-change orchestration;
- automatic migration of active runs to new engine versions.

---

# 29. Acceptance Criteria by Critical Product Invariant

## 29.1 Browser independence

Given a running project, when the user closes the browser and returns later, execution has either continued or entered a truthful engine/control state unrelated to the browser session.

## 29.2 Workspace durability

Given a worker restart, the canonical source/Git/checkpoint state remains available.

## 29.3 Truthful verification

Given a model statement claiming success while mechanical tests or verification fail, Kallula shows failure/unverified status.

## 29.4 Safe stop

Given a stop request while Siesta is within an active work item, Kallula shows `STOP_REQUESTED` until the adapter confirms Siesta reached a supported safe boundary.

## 29.5 Resume

Given a stopped run with a compatible checkpoint, resume continues against the same workspace rather than recreating source from the original prompt.

## 29.6 Engine isolation

Given an upstream Siesta phase-name or internal filename change covered by an updated adapter, the frontend and unrelated control-plane modules require no direct change to those native names.

## 29.7 Configuration reproducibility

Given a historical run and later changes to agent defaults, the historical run still shows the engine/profile/settings it actually used.

## 29.8 Secret isolation

Given control-plane GitHub/database secrets on the host, autonomous project workers cannot read them from inherited environment variables by default.

## 29.9 Source ownership

Given a completed or stopped project, the user can retrieve the canonical source without shell access.

## 29.10 Compatibility failure

Given a stored checkpoint that a newer Siesta/adapter cannot safely resume, Kallula reports incompatibility and does not silently attempt destructive migration.

---

# 30. Current Siesta Integration Findings That Affect Kallula Design

The following findings were observed in the reviewed Siesta `main` revision and should drive the first engine adaptation design. They are **not** permanent Kallula contracts.

## 30.1 Terminal-mediated human input

Current interview code calls terminal `input()` through `_read_answer()`. Kallula therefore needs a narrow external human-interaction seam.

## 30.2 Filesystem-native checkpointing

Current Siesta persists checkpoint and idea bookkeeping inside the project workspace. Kallula should preserve this engine-owned state while maintaining independent control-plane run state.

## 30.3 Safe stop through `stop.md`

Current safe-stop behavior checks a project-local stop file at issue boundaries. Kallula must translate a product stop request to the native mechanism through the adapter, not expose the file protocol to the frontend.

## 30.4 Fixed role configuration

Current Siesta loads Planner, Worker, and Consultant provider/model routes from `factory/config/models.json`. Kallula should model these as engine-exposed slots rather than permanently fixed product columns.

## 30.5 Full process-environment inheritance

Current Pi child construction returns the host environment plus a `PYTHONPATH` modification. That is unsuitable for hosted secret isolation and requires deliberate sanitization in the Kallula runner/adapter.

## 30.6 Native artifact filenames

Current Siesta exposes artifacts such as `spec.md`, `issues.md`, `verify_verdict.txt`, `.pipeline-checkpoint`, KB graphs, regression logs, and `.git/` state. Kallula should index them by artifact class instead of spreading filename assumptions through the product.

## 30.7 Strong mechanical gates

Current Siesta intentionally prevents empty tests, failed suites, unapproved review, unresolved issues, or failed runtime checks from becoming successful completion. Kallula must preserve these properties.

## 30.8 Git-based recovery

Current Siesta uses Git commits and recovery archives to keep blocked/unverified work from becoming the base for later issues. The canonical Git repository must remain intact and first-class.

## 30.9 Self-learning skill mutation

Current Siesta can apply learner-produced updates to selected factory skills. In Kallula, those mutations need versioning/audit/stability so one run cannot silently change another run's historical effective configuration.

## 30.10 KB single-writer assumption

Current Siesta documentation states concurrent writers to the same graph are unsupported. Initial Kallula design must preserve single-writer semantics for the engine-native workspace/KB.

---

# 31. Remaining Open Design Questions Requiring Separate Decisions

The foundational product, architecture, Siesta adaptation, UX, security, execution-runtime, and API/data-contract questions are now resolved by their normative supporting specifications.

In particular, the document set now fixes:

- Project/Run/Execution Attempt relationships and resume-versus-new-Run semantics;
- single-writer Project execution leases and crash reconciliation;
- adapter/engine boundaries and externally supplied canonical workspace behavior;
- durable Phase 0 suspension and Pending Interactions;
- normalized Stages, Work Items, Artifacts, Agent Slots, outcomes, and capability manifests;
- pinned-engine compatibility and upstream update policy;
- Run-scoped mutable Siesta learning assets;
- browser information architecture, attention/status behavior, responsive interaction, and current-versus-Verified-State presentation;
- browser session/object-authorization principles, credential domains, encryption, secret exposure, GitHub authority, redaction, audit, and Preview trust boundaries;
- hosted workload isolation, durable Workspace/Run Engine Runtime, Environment Snapshots, runtime packs, resource/network constraints, and separate Preview runtime;
- Runtime Plan/service/supporting-service model, stable Preview source, Gateway/origin/access, health/logging, cleanup, and runtime reconciliation;
- exact Kallula logical resources and persistence relationships;
- Run/Attempt/Interaction/Command/Event/Preview/Credential API representations;
- versioned REST and SSE transport;
- opaque IDs, timestamps, enum conventions, ETags, optimistic concurrency, cursor pagination, and idempotency;
- durable command semantics and distinction between command application and target lifecycle outcome;
- per-Run Event sequence/replay and account-level live invalidation behavior;
- security-sensitive write-only and never-returned API fields;
- standard error/problem contract and API compatibility/versioning rules.

The remaining work is now primarily validation, implementation selection, and implementation planning:

1. What exact test layers, fixtures, fakes, compatibility matrix, upgrade gates, recovery cases, concurrency tests, browser E2E tests, and security/runtime tests constitute the release gate?
2. Which selected real-Siesta/model smoke tests are required beyond deterministic fake-provider tests?
3. What exact authentication provider, relational database, ORM/query layer, session store, KeyProvider/KMS, OCI runtime driver, storage backend, firewall mechanism, Preview proxy, log store, audit store, and SSE fan-out implementation are selected for the first deployment?
4. Which curated runtime packs and supporting-service images ship in the first release?
5. What exact Environment Auto-detection rules are implemented first?
6. What exact existing-repository branch/pull-request policy is used?
7. What backup/restore products implement the already-defined consistency and key-recovery requirements?
8. How are resource/model-cost budgets measured and enforced?
9. Which notification channels ship initially and how are deliveries retried?
10. What future approval/promotion workflow, if any, turns Run-scoped learner changes into reusable shared profiles?
11. Under what coordination semantics, if any, may browser source editing coexist with autonomous execution?
12. How should future controlled steering alter requirements/specification/plan/checkpoints without violating engine recovery semantics?
13. What implementation milestones, dependency ordering, and Definitions of Done should be used to build the system incrementally?

These questions remain open deliberately. The **Test & Compatibility Strategy** should resolve the release/validation model next; the **Implementation Plan** should then resolve implementation sequencing and concrete first-release technology selections where they are not already constrained.


# 32. Required Supporting Documents Before Full Implementation

This PRD defines **what Kallula must do and what boundaries it must preserve**.

The next documents should resolve implementation domains rather than repeat this PRD.

Recommended order:

## 32.1 System Architecture & State Model

**Status: CREATED — normative architecture; implementation started.**

Document: [`Kallula — System Architecture & State Model.md`](./Kallula%20%E2%80%94%20System%20Architecture%20%26%20State%20Model.md)

It now defines:

- logical component/service boundaries without mandating microservices;
- Project, Run, and Execution Attempt lifecycle;
- precise resume-versus-new-Run semantics;
- canonical workspace ownership;
- one-active-writer Project execution leases;
- durable command/idempotency principles;
- worker lifecycle and attempt tracking;
- persistent control state ownership;
- crash detection and reconciliation behavior;
- normalized event durability and Run-local ordering principles;
- pending human interaction durability;
- current workspace versus Verified State semantics;
- engine installation/version pinning;
- capability-driven stage/artifact evolution;
- engine upgrade behavior;
- initial single-node/co-located deployment allowance;
- architectural invariants and acceptance criteria.

This document is now a prerequisite for the remaining implementation specifications and should be updated deliberately if later design work reveals a conflict with its invariants.

## 32.2 Kallula–Siesta Engine Adaptation Specification

**Status: CREATED — normative Siesta integration specification.**

Document: [`Kallula — Siesta Engine Adaptation Specification.md`](./Kallula%20%E2%80%94%20Siesta%20Engine%20Adaptation%20Specification.md)

It now defines:

- the adapter runtime boundary inside the Execution Worker;
- the minimum generic Siesta integration seams and standalone-CLI preservation rule;
- externally supplied canonical workspace behavior;
- cooperative durable Phase 0 suspension and restartable human interactions;
- structured engine event hooks and baseline event coverage;
- native-to-normalized stage/work-item/artifact mappings;
- structured engine terminal outcomes distinct from exit status;
- safe-stop translation and resume behavior;
- Native State Descriptor and explicit state-format identity;
- launch compatibility, state-format compatibility, and resume compatibility as distinct concepts;
- Planner/Worker/Consultant Agent Slot mapping and honest supported configuration fields;
- Run-scoped mutable factory skills and global learning context;
- explicit Pi child-environment filtering requirements;
- capability-manifest requirements and baseline capabilities;
- compatibility-suite acceptance requirements;
- upstream pin/patch/rebase and upgrade-gating policy.

This specification is subordinate to the PRD and System Architecture & State Model and must be updated alongside them if a future engine revision requires a genuine product/architecture change.

## 32.3 UX & Interaction Specification

**Status: CREATED — normative browser UX and interaction specification.**

Document: [`Kallula — UX & Interaction Specification.md`](./Kallula%20%E2%80%94%20UX%20%26%20Interaction%20Specification.md)

It now defines:

- global and Project information architecture;
- Dashboard attention hierarchy and Project summaries;
- complete initial screen inventory and secondary detail surfaces;
- new-Project and existing-repository creation flows;
- durable typed interview/pending-interaction behavior and final intent confirmation;
- Run/stage/Work Item presentation without conflating their states;
- safe-stop, confirmed-stop, resume, incompatibility, and recovery affordances;
- current workspace versus exact Verified State presentation;
- Activity, Work Items, Tests & Verification, Files, Git, Preview, and Runtime Log behavior;
- Agent Slot, Agent Profile, Environment, Credential, Knowledge, History, and Engine/System views;
- capability-driven controls and compatibility warnings;
- live-update freshness, reconnect, stale, empty, partial, and frontend-error behavior;
- desktop/compact/mobile priorities;
- accessibility and microcopy rules;
- UX acceptance criteria and traceability to the PRD, architecture, and Siesta adaptation specification.

The UX specification intentionally leaves visual branding, component-library selection, exact pixel breakpoints, GitHub authorization UX, advanced Environment fields, and credential/security mechanics to their owning later designs.



## 32.4 Security & Credentials Design

**Status: CREATED — normative security and credential-flow specification.**

Document: [`Kallula — Security & Credentials Design.md`](./Kallula%20%E2%80%94%20Security%20%26%20Credentials%20Design.md)

It now defines:

- threat model and trust classification;
- browser authentication/session and CSRF/origin requirements;
- server-side object authorization principles;
- credential domains: root/bootstrap, control-plane, integration, engine/provider, Project runtime, and ephemeral grants;
- metadata/value separation and no routine plaintext reveal;
- envelope encryption with per-value DEKs and separately managed KEK/root authority;
- key and credential rotation/revocation semantics;
- explicit Execution Worker and Siesta/Pi child-environment allowlists;
- model-provider credential exposure rules;
- Project-secret denial to coding agents by default;
- runtime-only secret injection semantics;
- GitHub App installation model and trusted integration execution path;
- Preview/control-plane origin, cookie, network, and secret separation;
- repository/filesystem/symlink/archive security requirements;
- logging prevention, redaction, secret scanning, and error-handling rules;
- audit-event requirements;
- backup/key recovery security;
- compromise-response flows;
- security compatibility gating and acceptance criteria.

The concrete authentication vendor, KMS/KeyProvider, worker sandbox, network-policy technology, Preview router, and redaction implementation remain replaceable implementation choices.


## 32.5 Execution Environment & Preview Design

**Status: CREATED — normative workload/runtime and Preview specification.**

Document: [`Kallula — Execution Environment & Preview Design.md`](./Kallula%20%E2%80%94%20Execution%20Environment%20%26%20Preview%20Design.md)

It now defines:

- hosted OCI-compatible workload isolation and development-only process mode;
- Runtime Manager boundary;
- durable canonical Workspace and Run Engine Runtime storage classes;
- immutable Engine Installation and Environment Snapshot attachment;
- curated runtime-pack strategy;
- worker mounts, resource limits, hardening, Attempt lifecycle, heartbeat, stop/resume, and failure classes;
- dependency/build containment;
- worker and Preview network zones;
- Runtime Plan, runtime detection, service dependencies, ports, and supporting services;
- separate Preview build and application-runtime phases;
- immutable committed Preview source snapshots;
- Preview Instance lifecycle, Gateway routing, separate production origin, and scoped access grants;
- service-scoped runtime credential injection;
- health checks, logs, backpressure, quotas, cleanup, and host/runtime reconciliation;
- initial single-host deployment and future multi-host portability boundary;
- runtime acceptance criteria.

Exact OCI product, storage backend, firewall technology, Preview proxy product/domain, runtime-pack contents, and log backend remain implementation choices within those constraints.


## 32.6 API & Data Contract Specification

**Status: CREATED — normative application/data contract specification.**

Document: [`Kallula — API & Data Contract Specification.md`](./Kallula%20%E2%80%94%20API%20%26%20Data%20Contract%20Specification.md)

It now defines:

- `/api/v1` versioned JSON REST plus SSE for replay/live delivery;
- opaque stable resource IDs and RFC 3339 UTC timestamps;
- resource versions/ETags and `If-Match` optimistic concurrency;
- required idempotency behavior for side-effecting POSTs;
- standard `application/problem+json` errors and stable error codes;
- Project, Workspace, Run, Run Configuration Snapshot, Execution Attempt, execution lease, Command, Pending Interaction, Interaction Response, Work Item, Event, Artifact, Verification Result, and Verified State contracts;
- Engine Installation/capability, Agent Profile/version, Environment Profile/version/Snapshot, Runtime Plan, Credential/value-version/assignment, Integration, Publish Operation, Preview/Preview Service, Knowledge, Notification, Audit, Export, and log-stream contracts;
- logical table/relationship/uniqueness/invariant requirements;
- durable command semantics;
- per-Run Event sequence, adapter-event deduplication, replay, and SSE semantics;
- account-level resource invalidation stream;
- Files/Git/source selector contracts;
- Preview immutable-source/update behavior;
- security-sensitive never-returned and write-only fields;
- transaction boundaries, derived-data rules, schema/API compatibility, and 40 API acceptance criteria.

The API specification deliberately leaves framework/database/ORM/runtime-library selection open while fixing behavior and data semantics.


## 32.7 Test & Compatibility Strategy

**Status: DEFERRED — required before release, not the next design document.**

Must define:

- control-plane tests;
- adapter contract tests;
- Siesta compatibility suite;
- end-to-end runs with fake model boundary;
- selected real-model smoke tests;
- recovery tests;
- security boundary tests;
- engine upgrade regression procedure.

---


## 32.8 Implementation Plan

**Status: CREATED — implementation execution guide.**

Document: [`Kallula — Implementation Plan.md`](./Kallula%20%E2%80%94%20Implementation%20Plan.md)

Translate the normative document set into vertical implementation milestones, dependencies, technology selections, migration/setup steps, and Definition of Done criteria. The plan must preserve the existing architecture rather than reopen it.

# 33. Product Success Criteria

Kallula is successful at its foundational stage if this scenario works reliably:

> A user opens Kallula in a browser, creates a project, answers requirements questions, inspects or accepts the proposed factory configuration, starts a Siesta-backed run, closes the browser, returns later from another device, sees exactly what has completed and what is happening now, understands whether the current source is verified, inspects work items/tests/Git/evidence, opens a generated application preview, safely stops or resumes execution when necessary, and ultimately retrieves or publishes the verified project without ever accessing the server directly.

The system must let the user answer:

- What did Kallula/Siesta understand?
- What engine version is running this project?
- What did it plan?
- What is it doing now?
- What needs my input?
- What has completed?
- What failed or became blocked?
- What tests actually ran and passed?
- What code changed?
- Which configuration produced this run?
- What is the last verified state?
- What can I preview right now?
- How do I retrieve or publish the source?
- Can this run safely resume?
- If Siesta changes, can Kallula adopt the change without rewriting unrelated product layers?

If those questions can be answered clearly, truthfully, and durably, the core product is working.

---

# 34. Final Product Definition

Kallula should evolve into:

> **A browser-based control plane for autonomous software development that uses Siesta as its initial software-factory engine while keeping projects, run state, configuration, runtime environments, execution evidence, source code, Git history, verification state, and human decisions persistent, observable, secure, and evolvable.**

The initial product equation is:

```text
Kallula
=
Stable product/control plane
+
Siesta engine adapter
+
Versioned Siesta engine
+
Durable project workspace
+
Run lifecycle and human interaction
+
Normalized events/artifacts
+
Agent/environment configuration
+
Credentials and trusted integrations
+
Git/source ownership
+
Preview and runtime visibility
+
Verification/provenance visibility
```

The primary development rule for all future work is:

> **Do not spread Siesta implementation details across Kallula. Preserve Siesta's proven reliability behavior, place engine-specific knowledge behind the integration boundary, pin execution to explicit engine/configuration versions, and introduce new infrastructure or abstraction only when a documented product requirement or discovered engineering constraint requires it.**

---

# Appendix A — Terminology

**Kallula** — The user-facing product and control plane defined by this PRD. **Siesta** — The initial autonomous software-development engine used by Kallula. **Engine** — The autonomous software-factory implementation responsible for planning/execution/review/verification semantics. **Adapter** — The Kallula integration layer translating between stable product contracts and engine-native behavior. **Project** — The durable software product/repository being created or maintained. **Run** — A bounded execution attempt against a project. **Workspace** — The canonical durable filesystem containing the actual project and engine-native project state. **Work Item** — A normalized planned/executed unit, currently corresponding to a Siesta issue where applicable. **Stage** — A normalized representation of engine execution progress. **Artifact** — A discoverable run/project evidence object mapped from native engine output/files. **Agent Slot** — An engine-exposed configurable role/function. **Agent Profile** — A named/versioned set of user-configurable agent settings. **Environment Profile** — A versioned description of the execution environment. **Verified State** — The most recent project state that successfully passed required verification gates.

# Appendix B — Traceability to the Initial PRD

This refined document preserves the strongest requirements from the initial *Siesta Cloud* PRD, including:

- browser-first operation;
- one authoritative workspace;
- Git as part of execution;
- structured observability;
- safe stop/resume;
- current vs verified state;
- source access/download;
- GitHub publishing;
- preview/runtime logs;
- configurable agents/environments;
- credential isolation;
- versioned run configuration;
- knowledge/provenance;
- deliberate deferral of complex steering and enterprise features;
- avoidance of premature infrastructure.

The most material refinement is the addition of an explicit **engine evolution contract** so Kallula can track upstream Siesta without making the rest of the product structurally dependent on the engine's current roles, phases, filenames, or terminal-oriented execution model.
