# Kallula — UX & Interaction Specification

**Document status:** Normative UX and interaction specification — implementation started
**Product:** Kallula
**Primary product specification:** [`Kallula — Product Requirements Document.md`](./Kallula%20%E2%80%94%20Product%20Requirements%20Document.md)
**Parent architecture:** [`Kallula — System Architecture & State Model.md`](./Kallula%20%E2%80%94%20System%20Architecture%20%26%20State%20Model.md)
**Engine adaptation specification:** [`Kallula — Siesta Engine Adaptation Specification.md`](./Kallula%20%E2%80%94%20Siesta%20Engine%20Adaptation%20Specification.md)
**Security & credentials design:** [`Kallula — Security & Credentials Design.md`](./Kallula%20%E2%80%94%20Security%20%26%20Credentials%20Design.md)
**Execution environment & Preview design:** [`Kallula — Execution Environment & Preview Design.md`](./Kallula%20%E2%80%94%20Execution%20Environment%20%26%20Preview%20Design.md)
**API & data contract specification:** [`Kallula — API & Data Contract Specification.md`](./Kallula%20%E2%80%94%20API%20%26%20Data%20Contract%20Specification.md)
**Implementation plan:** [`Kallula — Implementation Plan.md`](./Kallula%20%E2%80%94%20Implementation%20Plan.md)  
**Implementation status:** Tracked by the [Implementation Plan](./Kallula%20%E2%80%94%20Implementation%20Plan.md)
**Purpose:** Define the complete browser experience for Kallula: information architecture, screens, interaction semantics, attention states, capability-driven controls, responsive behavior, failure/recovery presentation, and user-visible truth rules.
**Audience:** Product, UX/UI, frontend, backend/control-plane, engine-integration, QA, accessibility, security, and infrastructure engineers.

> **Normative relationship:** The PRD defines what the product must do. The **System Architecture & State Model** defines state ownership, Run/Execution Attempt semantics, truth boundaries, persistence, and recovery. The **Siesta Engine Adaptation Specification** defines how current Siesta behavior is translated into stable Kallula concepts. The **Security & Credentials Design** defines the security policy behind authentication, credentials, integrations, Preview isolation, redaction, and audit. The **Execution Environment & Preview Design** defines the physical Environment Snapshot, worker runtime, stable Preview source identity, Runtime Plan, Preview lifecycle, routing/access, health, and runtime-secret behavior surfaced by this UX. The **API & Data Contract Specification** defines the exact frontend-facing resources, fields, commands, errors, ETags, idempotency, Event replay, and SSE/invalidation streams used to implement these interactions. This document remains authoritative for presentation and interaction behavior. If an interaction design would require violating a higher-level state, engine, security, runtime, or API invariant, the design must be reconciled deliberately.

> **UX truth rule:** The UI must never improve, simplify, or reinterpret backend truth into a more successful-looking state. `STOP_REQUESTED` is not `STOPPED`; a healthy preview is not a verified project; a model saying tests passed is not equivalent to mechanical test evidence; a lost connection is not completion; and current source is not automatically the last verified source.

> **Capability rule:** The frontend renders actions and configuration from Kallula product capabilities and engine-reported capabilities. It must not depend on current Siesta-native phase numbers, checkpoint filenames, stop files, or implementation markers.

---

# 1. Purpose

This specification turns Kallula's product, architecture, and Siesta-integration semantics into an implementable browser experience.

It answers:

- What pages and navigation structures exist?
- What information appears on each page?
- Which actions can a user perform from each state?
- How are Run state, engine stage, Work Item progress, Execution Attempts, and verification shown without conflating them?
- How does a pending Siesta interaction appear after the browser has been closed and reopened?
- How does the user safely request a stop and understand that it has not yet completed?
- How does resume differ visually from starting new work?
- How does a failed or incompatible Run explain what happened and what can be done next?
- How does the UI distinguish current mutable source from the exact last Verified State?
- How are files, Git history, tests, artifacts, knowledge, agents, environment settings, and credentials presented?
- How does the experience adapt to mobile browsers?
- Which states require explicit attention?
- How are unsupported capabilities represented?
- How are loading, stale, disconnected, empty, partial, and degraded states represented?

This document intentionally does not choose:

- a frontend framework;
- a component library;
- a CSS architecture;
- exact pixel breakpoints;
- an icon library;
- an API transport;
- a database schema;
- a live-update protocol;
- a preview-proxy technology;
- secret-storage technology;
- final branding colors or typography.

Those choices may be made later as long as the behavior and information hierarchy defined here remain intact.

---

# 2. UX Goals

Kallula's UX must make autonomous software development feel understandable and controllable rather than opaque.

The UX must optimize for the following outcomes.

## 2.1 Know what needs attention

From the Dashboard, a user should immediately see:

- which Projects are active;
- which Runs need human input;
- which Runs failed;
- which Runs are stopped;
- which Projects recently completed;
- which Project state is currently verified.

The user must not need to open every Project to discover whether action is required.

## 2.2 Know what the system is doing

For an active Run, the user should answer:

- What is the control state?
- What stage is the engine in?
- What Work Item is active?
- What happened recently?
- Are tests currently passing?
- Is a preview available?
- What configuration is this Run using?
- What is the last verified source state?

## 2.3 Know what is trustworthy

The UI must clearly distinguish:

- current workspace;
- current engine activity;
- engine/model narrative;
- mechanical evidence;
- final verification result;
- exact Verified State.

## 2.4 Leave and return safely

A user must close the browser without worrying that:

- execution will stop;
- a pending question will disappear;
- progress history will be lost;
- reconnecting will create duplicate actions.

## 2.5 Configure without becoming an infrastructure operator

Default paths should avoid requiring users to understand:

- containers;
- ports;
- worker hosts;
- filesystem paths;
- Pi internals;
- Siesta checkpoint files;
- provider transport details.

Advanced information remains available progressively.

## 2.6 Preserve expert visibility

Kallula is not a black box. Advanced users must still be able to inspect:

- engine identity;
- adapter identity;
- execution attempts;
- native stage identifiers where useful;
- logs;
- raw evidence;
- compatibility warnings;
- source and Git history.

---

# 3. UX Non-Goals

The initial Kallula UX is not:

- a full browser IDE;
- an unrestricted live chat with the coding agent;
- a drag-and-drop agent graph editor;
- an infrastructure dashboard;
- a Kubernetes console;
- a generic model playground;
- a GitHub replacement;
- a terminal emulator;
- a multi-user collaborative coding surface;
- a free-form prompt editor for engine protocol instructions.

The user may configure supported agent behavior, but engine-critical protocol content remains protected.

---

# 4. UX Principles

## 4.1 Product concepts first

Primary UI language must use Kallula concepts:

- Project;
- Run;
- stage;
- Work Item;
- pending interaction;
- Execution Attempt;
- Verified State;
- Agent Profile;
- Environment;
- Credential;
- Preview.

Current Siesta-native details may appear only in advanced diagnostics.

Do not make the default interface say:

- `phase-3`;
- `.pipeline-checkpoint`;
- `stop.md`;
- `verify_verdict.txt`;
- `SIESTA_FACTORY`.

## 4.2 State before activity prose

A stream of logs cannot substitute for explicit state.

Every active Project/Run surface must show its authoritative state independently from the activity feed.

## 4.3 Attention before chronology

The Dashboard prioritizes:

1. input required;
2. failure/recovery required;
3. stop requested;
4. active execution;
5. recent completion;
6. idle Projects.

A user should not have to inspect timestamps to infer urgency.

## 4.4 Evidence before confidence language

Avoid vague labels such as:

- Looks good;
- Probably passed;
- Almost done;
- 90% complete.

Prefer evidence:

- 42 tests passed;
- Verification passed at commit `18fa24`;
- 3 of 7 Work Items completed;
- Preview available, not verified;
- Waiting for your answer.

## 4.5 Capability-driven affordances

An action should appear only when it is:

- supported by the current product version;
- supported by the pinned Engine Installation when engine-dependent;
- valid for the current state;
- permitted for the current user.

Disabled controls should be used only when seeing the unavailable action is valuable. Otherwise, omit unsupported actions.

## 4.6 Progressive disclosure

Default views should stay understandable.

Advanced engine, adapter, attempt, native artifact, and diagnostics information should live behind secondary detail surfaces rather than dominate the main workflow.

## 4.7 Safe actions are easy; dangerous actions are deliberate

Viewing, answering, stopping safely, resuming when compatible, and opening evidence should be easy.

Potentially destructive or irreversible actions require:

- explicit naming;
- impact explanation;
- confirmation where appropriate.

## 4.8 Mobile is an operating surface, not a miniature desktop

Mobile must prioritize:

- attention;
- pending questions;
- current state;
- stop/resume;
- failures;
- preview access.

Dense source and Git inspection may simplify layout but must remain accessible.

---

# 5. User Model

The initial release assumes one authenticated owner or a very small ownership model.

The UX should avoid premature organization-management complexity.

The design must nevertheless avoid language that makes future ownership impossible. For example:

- say **Owner** rather than “local user”;
- show Project ownership metadata in advanced/settings areas;
- avoid hard-coding “My Project” as the domain identity.

---

# 6. User-Visible Terminology

The following terms are normative in the primary UI.

| Concept | Preferred UI term | Avoid in normal UI |
|---|---|---|
| Durable software product | Project | factory directory |
| Logical execution | Run | process |
| Worker lifetime | Execution Attempt | retry process |
| Engine progress unit | Stage | phase-3 |
| Planned implementation unit | Work Item | native issue unless intentionally shown |
| Durable human question | Pending interaction / Question | stdin request |
| Engine runtime version | Engine | Python pipeline |
| Exact trusted source checkpoint | Verified State | current files |
| Running generated application | Preview | exposed port |
| Runtime configuration | Environment | image/container unless advanced |
| Agent route/role | Agent Slot | hard-coded role schema |
| Credential metadata | Credential | environment variable value |
| Historical normalized event | Activity | stdout line |

Current Siesta's **Planner**, **Worker**, and **Consultant** names may be displayed as the current engine's Agent Slot labels because the adapter deliberately exposes them as current capabilities.

---

# 7. Global Attention Model

Kallula needs a consistent attention model across Dashboard, Project list, navigation, and notifications.

## 7.1 Attention levels

### Requires action

Used when the user must act before meaningful progress can continue.

Examples:

- pending interview question;
- incompatible resume requiring a decision;
- credential/configuration problem that blocks startup.

Primary label examples:

- **Needs your input**
- **Resume blocked**
- **Configuration required**

### Problem

Used for failed or degraded execution where action may be needed.

Examples:

- Run failed;
- preview failed;
- engine compatibility failure;
- publication failed.

Primary label:

- **Failed**
- **Needs recovery**

### In progress

Examples:

- starting;
- running;
- stop requested.

Labels:

- **Starting**
- **Running**
- **Stopping safely**

### Stable non-terminal

Examples:

- stopped;
- idle Project.

Labels:

- **Stopped**
- **Ready**

### Terminal success

Examples:

- Run completed.

Label:

- **Completed**

Completion must not imply a Verified State unless verification actually succeeded.

## 7.2 Ordering

When multiple signals exist, Project summary attention uses the strongest relevant signal.

Example:

```text
Run state: WAITING_FOR_HUMAN
Preview: failed
Last verified: available
```

Primary Project attention is **Needs your input**, while preview failure remains visible inside the Project.

## 7.3 Color is supplemental

Attention cannot rely only on color.

Every status uses:

- text label;
- icon or shape where appropriate;
- accessible state description.

---

# 8. Information Architecture

```text
Kallula
|
+-- Dashboard
+-- Projects
|   |
|   +-- Overview
|   +-- Run
|   |   +-- Current Run
|   |   +-- Work Items
|   |   +-- Activity
|   |   +-- Tests & Verification
|   +-- Code
|   |   +-- Files
|   |   +-- Git
|   +-- Application
|   |   +-- Preview
|   |   +-- Runtime Logs
|   +-- Factory
|   |   +-- Agents
|   |   +-- Environment
|   |   +-- Credentials
|   |   +-- Knowledge
|   +-- History
|   +-- Settings
+-- Settings
```


## 8.1 Global navigation

The initial global navigation is:

```text
Dashboard
Projects
Settings
```

`Settings` contains:

```text
Agent Profiles
Credentials
Integrations
Engine & System
Application
```

This keeps the global shell intentionally small.

## 8.2 Project navigation

A Project has the following top-level sections:

```text
Overview

Run
  ├── Current Run
  ├── Work Items
  ├── Activity
  └── Tests & Verification

Code
  ├── Files
  └── Git

Application
  ├── Preview
  └── Runtime Logs

Factory
  ├── Agents
  ├── Environment
  ├── Credentials
  └── Knowledge

History

Settings
```

If there is no current Run, the **Run** area displays the most recent Run plus the action to start new work where supported.

## 8.3 Navigation behavior

The current Project context persists while moving between its sections.

The user should not lose:

- Project identity;
- current attention state;
- current Run identity.

On desktop, Project navigation may be represented as a nested sidebar or secondary navigation rail.

On mobile, Project sections should collapse into a clear Project menu rather than squeezing all tabs horizontally.

## 8.4 Deep links

Each major view should have a stable navigable location so users can:

- refresh;
- bookmark;
- return from another device;
- follow notification links directly to a pending interaction/failure/Run.

Exact URL structure is deferred.

---

# 9. Global Application Shell

The application shell must provide:

- Kallula identity;
- current global location;
- Project context when inside a Project;
- attention indicator;
- account/settings access;
- connection/freshness status when degraded.

## 9.1 Desktop shell

A recommended structure:

```text
┌───────────────────────────────────────────────────────────────┐
│ Kallula        Search/Project switcher              Account   │
├───────────────┬───────────────────────────────────────────────┤
│ Dashboard     │                                               │
│ Projects      │                 Page content                  │
│ Settings      │                                               │
│               │                                               │
└───────────────┴───────────────────────────────────────────────┘
```

Inside a Project, the shell additionally exposes Project navigation.

## 9.2 Mobile shell

Recommended behavior:

- compact top bar;
- Project name/state;
- prominent attention banner when action is required;
- Project menu button;
- page-level primary action remains reachable without horizontal scrolling.

No essential status should exist only in desktop hover UI.

---

# 10. Page Header Pattern

Every major page should use a consistent header structure:

```text
[Context title]                        [Primary action]

[Short state summary / supporting metadata]

[Optional attention or trust banner]
```

For a Project:

```text
Expense Tracker                        Running

Execution — Work Item 4 of 7
Last verified: commit 18fa24
```

For a Run:

```text
Run #15                                Stop safely

Running · Execution
Started Oct 4, 2026 04:12
```

Run IDs may use friendly sequence labels while retaining stable internal identifiers behind the scenes.

---

# 11. Status Presentation

## 11.1 Run control state

The UI must support at least:

- Queued;
- Starting;
- Running;
- Needs your input;
- Stopping safely;
- Stopped;
- Failed;
- Completed.

The underlying normalized state may remain visible in diagnostics.

## 11.2 Stage

Stage is shown independently from Run state.

Example:

```text
Run
Running

Stage
Execution
```

A Run can therefore be:

```text
Needs your input
Stage: Requirements
```

## 11.3 Stage progression

The stage rail/timeline is generated from engine capabilities/topology.

It must not assume Siesta always has a fixed number of stages.

Current Siesta may appear as:

```text
✓ Requirements
✓ Specification
✓ Planning
● Execution
○ Review
○ Verification
○ Learning
```

If a future engine changes topology, the UI must render the supplied normalized stage model.

## 11.4 Progress

Before a meaningful count exists, use categorical state only.

Once Work Items exist:

```text
3 of 7 Work Items completed
```

Do not derive a percentage unless the product defines a defensible calculation.

## 11.5 Execution Attempt

Execution Attempts are secondary operational detail.

Default Run view may show:

```text
Current attempt: #3
```

The full attempt timeline belongs under diagnostics/details.

---

# 12. Verified State Presentation

Verified State is one of the most important trust concepts in Kallula.

Every relevant Project/Run surface must distinguish:

```text
Current workspace
Last verified state
```

## 12.1 When current equals verified

Show:

```text
Verified
commit 18fa24
42 tests passed
```

## 12.2 When current is ahead of verified

Show:

```text
Current workspace
Changing — not yet verified

Last verified
commit 18fa24
42 tests passed
```

## 12.3 No Verified State yet

Show:

```text
No verified state yet
The current source has not completed verification.
```

## 12.4 Preview relationship

A Preview card may say:

```text
Available
Current workspace preview

Not yet verified
```

Never show a generic green success treatment that could imply verification.

---

# 13. Capability-Driven UX

Every engine-dependent action has one of these capability states:

- supported and currently valid;
- supported but invalid in current state;
- unsupported by this Engine Installation;
- unavailable because compatibility is uncertain;
- unavailable because required configuration is missing.

## 13.1 Unsupported capabilities

Prefer explaining absence where the user would reasonably expect the action.

Example:

```text
Restart Work Item
Not supported by this Engine Installation.
```

For advanced/deferred features, simply omit them from the normal UI.

## 13.2 Compatibility warnings

Warnings must identify:

- affected operation;
- Engine Installation;
- whether the problem is launch, state-format, or resume compatibility;
- safe next action.

Do not reduce this to “Something went wrong.”

---

# 14. Live Updates, Freshness, and Reconnect

## 14.1 Live state

Active Run views should update automatically under normal conditions.

## 14.2 Durable replay

After reconnect, the frontend must reconstruct from durable state/events rather than assuming missed live messages are lost.

## 14.3 Freshness indicator

When the browser cannot confirm current backend state, show an explicit degraded indicator such as:

```text
Connection interrupted
Showing last known state from 05:17:32.
Reconnecting…
```

Do not continue animating “Running” as if it were fresh truth without qualification.

## 14.4 Reconnected state

On successful reconnect:

- refresh authoritative Run state;
- replay missing events;
- remove stale banner;
- preserve the user's current page/scroll context where practical.

---

# 15. Authentication View

The initial authentication surface should be minimal.

Required behavior:

- clearly identify Kallula;
- support configured authentication method;
- preserve the requested deep link after successful authentication;
- show authentication errors without exposing sensitive backend details.

Multi-organization selection is not required in v1.

---

# 16. Dashboard

The Dashboard answers:

- What needs me?
- What is running?
- What recently changed?
- What is the trusted state of my Projects?

## 16.1 Default structure

Recommended:

```text
Dashboard

Needs attention
  [Project A — Needs your input]
  [Project B — Failed]

Active
  [Project C — Running — Execution — Work Item 4/7]

Recent
  [Project D — Completed]
  [Project E — Stopped]
```

If there are no attention items, omit the section rather than showing a large empty warning area.

## 16.2 Project card/list content

At minimum:

- Project name;
- primary attention/control state;
- current stage when active;
- current Work Item summary where useful;
- last meaningful timestamp;
- last Verified State indicator;
- primary context action.

Example:

```text
Expense Tracker
Running · Execution · Work Item 4 of 7
Last verified: Work Item 3 · 42 tests · 18fa24
Updated 1 min ago

[Open run]
```

## 16.3 Needs-input card

Example:

```text
Inventory Tool
Needs your input · Requirements

“Should authentication support email/password only,
or should social login be included?”

[Answer now]
```

do not need opening the full Run page before answering.

## 16.4 Failed card

Example:

```text
Reporting App
Failed · Verification

Runtime smoke check failed.
Last verified: Work Item 5 · commit 77b9d1

[Review failure]
```

## 16.5 Empty Dashboard

For a new account:

```text
No Projects yet
Create a Project to start building with Kallula.

[Create Project]
```

Avoid fake demo metrics.

---

# 17. Projects List

The Projects page provides the complete Project inventory.

## 17.1 Required columns/content

Desktop may use a table or dense list with:

- Project;
- state/attention;
- active or latest Run;
- stage;
- last verified;
- updated time;
- optional source origin indicator.

Mobile should use cards/rows.

## 17.2 Filtering

Initial useful filters:

- All;
- Needs attention;
- Running;
- Stopped;
- Failed;
- Completed/Idle.

Search by Project name may be provided.

Advanced filtering is not required.

## 17.3 Sorting

Default:

1. requires action;
2. problem;
3. active;
4. recently updated.

User-selectable sorting is optional for initial release.

---

# 18. Create Project Flow

Project creation is a focused flow, not a settings dump.

## 18.1 Step 1 — Starting point

```text
Create Project

How do you want to start?

● Describe a new project
○ Use an existing repository
```

Only show repository mode when supported/configured.

## 18.2 New Project — Describe goal

Required field:

```text
What do you want to build?
[ multi-line request ]
```

Helpful guidance may mention:

- intended user;
- major behavior;
- important constraints.

Do not force the user to write a formal specification.

## 18.3 Build mode

```text
How should Kallula clarify the project?

● Interview me
  Ask focused questions before autonomous work starts.

○ Use sensible defaults
  Let the engine resolve missing details autonomously where supported.
```

The exact labels should make delegation explicit.

Do not call the second option “Skip requirements” because requirements still exist.

## 18.4 Factory configuration

Default presentation:

```text
Factory configuration

Agent profile
[ Default ▾ ]

Environment
[ Auto ▾ ]

Advanced configuration
[Show]
```

Engine/adapter version is not a normal creation choice unless multiple supported installations are intentionally exposed.

Advanced users may inspect the chosen Engine Installation before start.

## 18.5 Review

Before creating the first Run, show:

- starting point;
- Project request/repository;
- clarification mode;
- Agent Profile;
- Environment mode;
- engine summary;
- any compatibility/configuration warnings.

Primary action:

Interactive:

```text
[Create Project & begin interview]
```

Autonomous:

```text
[Create Project & start run]
```

## 18.6 Submission behavior

After submission:

- Project creation becomes durable before long execution starts;
- navigation moves to the relevant Project/Run screen;
- long-running engine startup must not block the browser request;
- duplicate submission must not create duplicate Runs.

## 18.7 Creation failure

If durable Project creation fails, remain in the flow and preserve user-entered non-sensitive fields where practical.

If Project succeeds but Run launch fails, navigate to the created Project and show the failed Run truthfully rather than pretending creation failed entirely.

---

# 19. Existing Repository Import Flow

This flow is available only when repository integration/import capability is supported.

## 19.1 Required sequence

```text
Connect/select repository
    ↓
Choose branch/revision
    ↓
Review working-branch behavior
    ↓
Choose clarification mode
    ↓
Choose Agent Profile / Environment
    ↓
Create Project
```

## 19.2 Repository identity

Show:

- repository owner/name;
- source host;
- selected branch/revision;
- whether history will be preserved.

## 19.3 Branch safety

Before starting, explain that Kallula will work on a dedicated working branch where policy supports it.

Never imply that default branch will be modified directly if that is not the configured policy.

Final publish/PR behavior remains dependent on the later GitHub/security design.

---

# 20. Project Shell

Every Project page should preserve a compact Project context header.

Example:

```text
Expense Tracker
Running · Execution
Last verified: 18fa24

[Open current run] [Preview]
```

If attention is required:

```text
Inventory Tool
Needs your input

[Answer question]
```

The Project shell should not repeat a large full status card on every subpage; instead use a compact consistent context plus page-specific content.

---

# 21. Project Overview

The Project Overview is the landing page for a Project.

It should answer:

- What is this Project?
- What is happening now?
- What is the trusted state?
- What should I do next?
- What recent Runs exist?

## 21.1 Primary sections

Recommended:

```text
Project status
Current / latest Run
Last Verified State
Application Preview
Recent activity
Recent Runs
Factory summary
```

## 21.2 No Run yet

Show Project configuration and:

```text
No Run has started yet.

[Start first Run]
```

only when valid.

## 21.3 Active Run

Show:

- Run state;
- stage;
- Work Item;
- Work Item progress;
- latest tests;
- stop action when valid;
- pending interaction if any.

## 21.4 Completed Run

Show clear result actions:

```text
[Open Preview]
[View Code]
[Download Source]
[View Git]
[Publish]
```

Only show supported/configured actions.

---

# 22. Interview / Pending Interaction

This is a controlled interaction surface, not a free-form agent chat.

## 22.1 Interaction layout

Recommended:

```text
Requirements interview

Question 3

What should happen when a user's session expires?

Engine recommendation
Use server-side sessions and redirect to sign-in,
preserving the intended destination.

[Your answer ........................................]

[Submit answer]

[Use the recommendation]
[Let Kallula decide the remaining questions]   (only when supported)
```

## 22.2 Context

The page may show prior accepted question/answer pairs in a compact transcript.

Rejected engine draft summaries or internal protocol text should not confuse the user.

## 22.3 Durable waiting

When reopened from another device, show the exact pending interaction and its current state.

Do not show a generic “Run paused.”

## 22.4 Answer submission

After submission:

- disable duplicate immediate submission;
- display a local “Answer submitted” state only after backend acceptance;
- transition to processing/restarting state;
- if the new Execution Attempt is queued, say so truthfully.

Example:

```text
Answer received
Kallula is continuing the same Run.
```

## 22.5 Final intent confirmation

When the engine proposes final intent, the UI must clearly distinguish this from an ordinary question.

Example:

```text
Confirm project intent

Kallula understands the project as:

[summary]

[Confirm intent]
[Request a change]
```

`Request a change` provides a focused correction field.

The user must not be forced to type “yes”.

## 22.6 Delegate remaining decisions

If supported:

```text
Let Kallula decide the remaining interview questions using sensible defaults.
```

This action requires a lightweight confirmation explaining that the remaining clarification will proceed autonomously.

## 22.7 Interaction no longer active

If another accepted action resolves the interaction before this browser submits:

```text
This question has already been answered.
[View current Run]
```

Do not silently overwrite.

---

# 23. Current Run Overview

This is the primary operating screen during execution.

## 23.1 Required summary

At minimum:

- Run control state;
- current normalized stage;
- current Work Item;
- Work Item completion count;
- recent activity;
- latest test state;
- preview state;
- Agent Profile summary;
- Environment summary;
- Engine summary;
- last Verified State;
- valid control actions.

## 23.2 Recommended layout

Desktop:

```text
Run #15                                       [Stop safely]

Running · Execution
Work Item 4 of 7 — CSV Import

Stages
✓ Requirements  ✓ Specification  ✓ Planning  ● Execution  ○ Review  ○ Verification

Current Work Item
CSV Import
Worker is running tests

Latest tests
31 passed · running again

Last Verified State
Work Item 3 · commit 18fa24 · 42 passed

Preview
Available · current workspace · not yet verified

Recent activity
05:14 Work Item 4 started
05:15 importer.py modified
05:16 regression tests started
...
```

## 23.3 Mobile priority

Order:

1. attention/control state;
2. pending interaction if any;
3. safe stop/resume;
4. stage;
5. Work Item;
6. last verified;
7. tests;
8. preview;
9. recent activity.

Agent/environment details may collapse.

## 23.4 Waiting for human

The Run Overview must place the pending interaction prominently at the top with **Answer now**.

## 23.5 Stop requested

Replace the Stop button with:

```text
Stopping safely…
Kallula asked the engine to stop at the next supported safe boundary.
Work may continue until that boundary is reached.
```

Do not offer Resume while `STOP_REQUESTED`.

---

# 24. Work Items

The Work Items view exposes the engine-generated implementation plan in normalized form.

## 24.1 List

Example:

```text
1  Project scaffold       Completed
2  Database layer         Completed
3  Expense CRUD           Completed
4  CSV import             Running
5  Filtering              Pending
6  Reporting              Pending
7  Integration            Pending
```

## 24.2 Work Item detail

Where data exists, show:

- title;
- description;
- acceptance criteria;
- dependencies;
- state;
- attempts;
- consultations;
- blockers;
- test evidence;
- commit/reference;
- related Activity.

## 24.3 State truth

A Work Item is not shown as completed solely because model prose says it is complete.

If model narrative and mechanical state disagree, the UI follows normalized authoritative state and may expose the disagreement in diagnostics.

## 24.4 Blocked Work Item

Show blocker reason and whether:

- the Run continued;
- the Run failed;
- user action is available.

Do not invent a retry button unless current capabilities support one.

---

# 25. Activity

The Activity page is a durable event history, not raw logs.

## 25.1 Event examples

```text
05:14  Execution started
05:14  Work Item 4 started
05:15  Source changed
05:16  Regression tests started
05:16  31 tests passed
05:17  Consultation requested
05:18  Consultation completed
05:19  Commit created — 18fa24
```

## 25.2 Event detail

An event may expose:

- timestamp;
- source: Kallula / adapter / engine;
- related stage;
- Work Item;
- Execution Attempt;
- artifact/evidence links;
- raw diagnostic reference when safe.

## 25.3 Filtering

Useful initial filters:

- All;
- Run;
- Work Items;
- Tests;
- Git;
- Interactions;
- Errors.

Raw engine log filtering belongs to diagnostics/runtime logs, not this normalized Activity view.

## 25.4 Live feed

New events append live while preserving the user's scroll position.

If the user is reading older history, do not jump the viewport automatically; show “New activity” affordance.

---

# 26. Tests & Verification

This screen must make evidence quality explicit.

## 26.1 Summary

Show:

- current/latest test result;
- latest verification result;
- relationship to current source;
- relationship to Verified State.

Example:

```text
Current workspace
Latest regression suite: 31 passed
Verification: not yet run for current workspace

Last Verified State
commit 18fa24
Verification passed
42 tests passed
Runtime smoke check passed
```

## 26.2 Test run detail

Where available:

- type;
- stage/Work Item;
- start/end time;
- pass/fail/skip counts;
- command/context where safe;
- related commit/source identity;
- artifact/log.

## 26.3 Model-reported evidence

If engine/model narrative exists without mechanical proof:

```text
Agent report
“Tests look good.”

Not mechanical verification
```

It must not share the same success badge as actual test execution.

## 26.4 Verification failure

Show:

- exact failed gate;
- evidence;
- current source identity;
- previous Verified State;
- valid recovery actions.

---

# 27. Files

The Files screen browses the canonical workspace.

## 27.1 Layout

Desktop:

```text
File tree | File viewer
```

Mobile:

```text
File picker / breadcrumb
File viewer
```

## 27.2 Required behavior

- directory navigation;
- syntax-readable content;
- path/breadcrumb;
- file size/metadata where useful;
- current source identity;
- read-only treatment during autonomous execution.

## 27.3 Current vs verified

The default source view is current canonical workspace.

Provide a clear indicator:

```text
Viewing: Current workspace
Not yet verified
```

Where supported, allow switching to:

```text
Last Verified State
```

without implying a second independent workspace.

## 27.4 Active changes

If a file may change while being viewed:

```text
This file changed while you were viewing it.
[Reload current version]
```

Do not silently replace content mid-read.

## 27.5 Editing

No editing controls in the initial release.

---

# 28. Git

Git is a first-class Project view.

## 28.1 Required summary

- current branch;
- working-tree state;
- commit history;
- latest verified commit;
- remote/publish status where applicable.

## 28.2 Commit history

Example:

```text
18fa24  Work Item #3 — expense CRUD
0ee217  Work Item #2 — database layer
774cad  Intent captured
```

## 28.3 Commit detail

Where supported:

- commit metadata;
- related Work Item;
- verification relationship;
- changed files/diff.

Diff inspection may be included if feasible; it is not a full editor.

## 28.4 Working tree

Show whether current workspace has uncommitted/unverified changes.

Do not translate “dirty” into failure automatically; it may be normal during execution.

---

# 29. Preview

Preview is an application runtime surface, not a verification badge.

## 29.1 Preview states

The UI must support:

- Not runnable;
- Starting;
- Available;
- Unavailable;
- Failed;
- Stopped.

## 29.2 Available state

Show:

```text
Preview available

Source: latest committed Project state
Not yet verified

[Open preview]
```

## 29.3 Failed state

Show:

- failure summary;
- runtime/service context where safe;
- link to Runtime Logs;
- whether Run execution continues independently.

## 29.4 Embedded vs separate window

Exact rendering is a UI implementation choice.

The product must support opening the application safely without requiring the user to know ports or hostnames. The source-snapshot, Gateway, separate-origin, scoped-access, health, and runtime lifecycle are defined by [`Kallula — Execution Environment & Preview Design.md`](./Kallula%20%E2%80%94%20Execution%20Environment%20%26%20Preview%20Design.md).

## 29.5 Mobile

Prefer opening Preview in a dedicated full-screen/browser context rather than embedding a tiny desktop iframe.

---

# 30. Runtime Logs

Runtime Logs are distinct from normalized Activity.

They show application/service runtime evidence.

## 30.1 Required capabilities

- select service/process where multiple exist;
- view recent logs;
- indicate log freshness;
- show startup command/context where safe;
- show redaction indicator when applicable.

## 30.2 Failure emphasis

If Preview failed, link directly to the relevant log segment when available.

## 30.3 Sensitive content

The UI must never provide a “show unredacted secret” path.

Redaction policy is defined by the Security & Credentials Design; the runtime/logging implementation must enforce it.

---

# 31. Agents

The Agents page configures engine-exposed Agent Slots.

## 31.1 Page structure

```text
Agent Profile
[ Default v3 ▾ ]

Engine slots
Planner
Worker
Consultant
```

Slots come from engine capabilities.

## 31.2 Slot card/detail

Show supported fields only.

Possible fields:

- provider;
- model;
- thinking/reasoning level;
- editable behavioral instructions;
- editable engineering guidance;
- skills;
- validation status.

## 31.3 Locked configuration

Engine protocol instructions are displayed, if at all, as protected system configuration:

```text
Engine protocol
Managed by the Engine Installation
Not editable
```

Do not show an editable text area for protected protocol content.

## 31.4 Unsupported combinations

Validation failure should explain the reason:

```text
This model cannot be used for the Worker slot because native file/shell
tool support has not been validated for this Engine Installation.
```

## 31.5 Active Run immutability

When viewing an active/historical Run:

```text
Run configuration snapshot
Read-only
```

Project default changes affect future Runs only.

---

# 32. Environment

Environment configuration is presented in progressive layers.

## 32.1 Default state

```text
Environment
Auto

Kallula will determine a supported environment after it understands the project.
```

## 32.2 Proposed/resolved environment

Example:

```text
Python 3.12
Node 22
PostgreSQL
Memory: 4 GB
Outbound network: enabled
Application services: frontend, backend
```

Do not expose implementation-specific image IDs in the primary summary.

## 32.3 Advanced configuration

Where supported:

- runtime versions;
- system dependencies;
- supporting services;
- resources;
- network policy;
- preview/service declarations.

The editable model is constrained by [`Kallula — Execution Environment & Preview Design.md`](./Kallula%20%E2%80%94%20Execution%20Environment%20%26%20Preview%20Design.md); the UI edits supported Environment Profile/Runtime Plan fields rather than raw container privileges.

## 32.4 Historical Run

Environment snapshot for a historical Run is read-only and includes version/identity information sufficient for attribution.

---

# 33. Project Credentials

The Project Credentials view manages permissions/assignments, not secret revelation.

## 33.1 Assignment list

Example:

```text
Project credentials

OPENAI_API_KEY        Assigned
SUPABASE_KEY          Assigned
STRIPE_SECRET_KEY     Not assigned
```

## 33.2 Actions

Where permitted:

- assign;
- unassign;
- add new credential;
- rotate/replace via global credential workflow.

## 33.3 Secret value

After creation, display only metadata:

- name;
- type/category;
- last updated;
- assignment status;
- validation status if available.

No routine reveal action.

## 33.4 Agent exposure

If initial product does not expose arbitrary project credentials to coding agents, communicate that clearly:

```text
Assigned for Project runtime use.
Not exposed to autonomous coding agents by default.
```

The Security & Credentials Design defines the underlying assignment and exposure semantics.

---

# 34. Knowledge

The Knowledge view surfaces engine/project knowledge without inventing a second semantic store.

## 34.1 Categories

Useful normalized categories:

- Intent;
- Decisions;
- Consultations;
- Proxy decisions;
- Blockers;
- Work Item completion;
- Learning.

## 34.2 Detail

Each entry may show:

- summary;
- detail;
- time;
- related Run;
- related Work Item;
- provenance links.

## 34.3 Advanced/native data

Engine-native node IDs/types may appear under advanced detail, not as primary labels.

---

# 35. Run History

Run History shows logical Runs, not individual worker processes.

## 35.1 List

Example:

```text
Run #15   Running       Oct 4
Run #14   Completed     Oct 3
Run #13   Failed        Oct 2
Run #12   Stopped       Oct 1
```

## 35.2 Run summary

Show:

- purpose/request when available;
- terminal/current state;
- engine/adapter identity;
- Agent Profile snapshot;
- Environment snapshot;
- start/end;
- verification result;
- Verified State created, if any;
- Execution Attempt count.

## 35.3 Execution Attempts

Attempts are visible within Run detail:

```text
Attempt #1  Ended — waiting for human
Attempt #2  Failed — worker lost
Attempt #3  Running
```

This reinforces that an Attempt restart is not a new Run.

## 35.4 Historical immutability

Configuration shown for historical Runs is read-only.

---

# 36. Project Settings

Project Settings contains Project-scoped defaults and management.

Initial categories:

- Project identity/display name;
- default Agent Profile;
- default Environment;
- engineering preferences;
- repository/source settings;
- advanced engine information;
- ownership metadata.

Changes must clearly state whether they affect:

- future Runs;
- current Project metadata;
- current Run.

Never imply historical Run mutation.

---

# 37. Global Agent Profiles

Users can manage reusable named Agent Profiles.

## 37.1 List

Show:

- profile name;
- version;
- compatible Engine Installations/capabilities where relevant;
- last updated;
- default indicator.

## 37.2 Edit behavior

Saving a meaningful configuration change creates a new effective version/snapshot.

UI should communicate:

```text
Saving these changes will create Default v4.
Existing Runs remain on their original configuration.
```

## 37.3 Duplicate

Allow duplicating a profile where useful.

Arbitrary agent creation is not required; profiles configure exposed slots.

---

# 38. Global Credentials

Global Credentials manages stored credential metadata.

## 38.1 List

Show:

- name;
- credential domain/type;
- updated time;
- assignment count;
- validation state where available.

## 38.2 Create credential

Flow:

```text
Name
Type/category
Secret value
Optional metadata
[Save credential]
```

After save, the value cannot be routinely revealed.

## 38.3 Replace/rotate

Replacing a credential should make impact clear:

```text
This updates the stored credential used by 2 Projects.
Historical Run metadata will not store the secret value.
```

Credential rotation/revocation semantics are defined by the Security & Credentials Design; active-runtime restart behavior is finalized by the Execution Environment & Preview Design.

## 38.4 Delete

Deletion requires confirmation and should list affected assignments.

---

# 39. Integrations

Integrations are Kallula-owned service connections such as GitHub.

The page should distinguish:

- connected;
- needs attention;
- disconnected;
- unsupported/not configured.

Do not mix platform integration credentials with Project Credentials.

GitHub authorization follows the Security & Credentials Design's GitHub App installation model; final repository-permission and publish/PR interaction details may be refined with the API/integration implementation.

---

# 40. Engine & System

This is an advanced settings/diagnostics surface.

## 40.1 Engine Installations

Show supported installed engine combinations:

- engine name;
- upstream revision/version;
- adapter version;
- compatibility status;
- capability summary;
- default/new-Run eligibility.

## 40.2 Compatibility status

Example:

```text
Siesta
Revision: 20b149e…
Adapter: 1.x

Launch compatibility: Supported
State format: Supported
Resume compatibility: Supported for matching pinned Runs
```

A warning must be explicit if one dimension differs.

## 40.3 Historical pinning

From a Run detail, link to its exact Engine Installation.

## 40.4 Native diagnostics

Advanced detail may show:

- native stage IDs;
- native artifact references;
- raw engine evidence;
- runtime health.

This is diagnostic, not primary navigation.

---

# 41. Safe Stop Interaction

Safe stop is a core operation with explicit semantics.

## 41.1 Entry point

Available from Current Run Overview and relevant Project header when the Run supports safe stop.

Button:

```text
Stop safely
```

Not:

- Kill;
- Cancel immediately;
- Pause.

## 41.2 Confirmation

For the initial issue-boundary semantics, use a concise confirmation:

```text
Stop this Run safely?

Kallula will ask the engine to stop at the next supported safe boundary.
The current operation may continue for a while before the Run is fully stopped.

[Keep running] [Request safe stop]
```

## 41.3 Requested state

After durable command acceptance:

```text
Stopping safely

The stop request is recorded.
Kallula is waiting for the engine to reach a supported safe boundary.
```

The user may leave the page.

## 41.4 Confirmed stop

Only after engine confirmation:

```text
Stopped safely
The Project workspace and checkpoint were preserved.

[Resume Run]
```

if resume is compatible.

## 41.5 Worker loss during stop

If the worker disappears before stop confirmation:

```text
Stop outcome uncertain

The worker stopped responding before the engine confirmed a safe boundary.
Kallula is reconciling the workspace.
```

Do not convert this to `Stopped`.

---

# 42. Resume Interaction

## 42.1 Resume availability

Show Resume only when:

- Run is in an eligible state;
- no conflicting active Project execution lease exists;
- pinned Engine Installation is available;
- compatibility check permits resume.

## 42.2 Resume confirmation

Example:

```text
Resume Run #15?

Kallula will continue this Run from its existing workspace and engine state.
It will not recreate the Project from the original request.

Engine: Siesta 20b149e…
Last checkpoint: Execution
Current workspace preserved

[Cancel] [Resume]
```

## 42.3 After resume

Show:

```text
Continuing Run #15
Starting a new Execution Attempt…
```

Do not create the impression of a new Run.

## 42.4 Incompatible resume

Example:

```text
This Run cannot be resumed safely.

The pinned engine state is not compatible with the available Engine Installation.
Kallula has preserved the workspace and history.

[View compatibility details]
[View source]
```

Do not offer “Try anyway” in the initial product.

---

# 43. Failure and Recovery UX

A failure screen/card must identify:

- failed stage;
- Work Item if known;
- failure class where useful;
- concise user-facing explanation;
- evidence/log links;
- current workspace state;
- last Verified State;
- available recovery actions.

## 43.1 Example

```text
Run failed

Stage: Verification
Work Item: —

Runtime smoke check failed because the application exited during startup.

Current workspace
Unverified

Last verified
commit 18fa24 · 42 tests passed

[View evidence]
[Runtime logs]
[Resume]   (only if supported)
```

## 43.2 Failure classes

Primary wording may distinguish:

- Engine failed;
- Execution worker failed;
- Adapter/integration failed;
- Configuration invalid;
- Compatibility problem.

Do not expose stack traces as the primary explanation.

## 43.3 Recovery action rules

Never display Retry/Resume generically.

Use capability/state-specific actions:

- Resume;
- Reconfigure and start a new Run;
- View source;
- Download source;
- View compatibility details.

Future “restart current Work Item” remains deferred unless explicitly supported.

---

# 44. Configuration Snapshot UX

Every Run detail must allow inspection of its immutable effective configuration.

Sections:

- Engine Installation;
- Agent Profile snapshot;
- slot/model/provider assignments;
- Environment snapshot;
- permitted credential names;
- Project engineering preferences snapshot;
- relevant skill identities/versions.

Sensitive values are never shown.

The page should state:

```text
This configuration belongs to Run #15 and is read-only.
Changing Project defaults will not change this Run.
```

---

# 45. Notifications and Attention Entry Points

The product requirement is to notify when unattended work needs attention or reaches a meaningful terminal state.

This UX specification defines the destination behavior even though delivery channels are still open.

Notification-worthy states include:

- pending human interaction;
- Run failed;
- verification failed;
- Run completed;
- Run stopped after a stop request;
- compatibility/recovery requires user action.

Every notification should deep-link to the exact Project/Run/interaction.

Browser/in-app attention indicators must remain available even if email is not yet implemented.

---

# 46. Loading, Empty, Error, and Partial States

Every view must define meaningful non-happy states.

## 46.1 Loading

Use skeleton/progress treatment for short data retrieval.

Do not use an indefinite “Working…” screen for long engine activity. Long activity belongs to explicit Run state plus Activity.

## 46.2 Empty

Empty states explain what the absence means and offer the next valid action.

Examples:

```text
No Work Items yet
The implementation plan has not been created.
```

```text
No Verified State yet
This Project has not completed verification.
```

## 46.3 Partial data

If normalized state exists but an optional artifact is missing:

```text
Run completed, but detailed test artifact is unavailable.
```

Do not invent replacement content.

## 46.4 Fetch error

Differentiate:

- page data could not load;
- Run itself failed.

A frontend/API fetch failure must not change the displayed Run state to Failed.

## 46.5 Unsupported feature

Use explicit capability language rather than generic errors.

---

# 47. Confirmation and Destructive Action Patterns

Actions requiring confirmation include at least:

- request safe stop;
- delegate remaining interview decisions;
- delete credential;
- disconnect integration when it affects active configuration;
- destructive Project deletion if/when implemented.

Routine navigation and answer submission should not require excessive confirmations.

Confirmation language must name the object and consequence.

Avoid:

```text
Are you sure?
```

Prefer:

```text
Delete credential STRIPE_SECRET_KEY?
3 Projects currently reference it.
```

---

# 48. Read-Only and Mutable State Patterns

The UI must clearly identify whether the user is editing:

- Project defaults;
- global reusable profile;
- immutable Run snapshot;
- current Project credential assignment;
- Engine Installation diagnostics.

Use labels such as:

```text
Project default — applies to future Runs
```

```text
Run snapshot — read-only
```

This distinction is especially important on Agents and Environment pages.

---

# 49. Responsive Behavior

Exact breakpoints are implementation details. UX is defined in three layout classes:

- wide;
- compact;
- narrow/mobile.

## 49.1 Wide

Can use:

- persistent global sidebar;
- Project secondary navigation;
- split panes;
- dense tables.

## 49.2 Compact

May collapse secondary navigation and reduce side-by-side panels.

## 49.3 Narrow/mobile

Requirements:

- one primary column;
- status and primary action near top;
- no horizontal dependency for essential actions;
- tables become cards/lists;
- source tree becomes selectable drawer/list;
- dialog content remains usable without zoom;
- pending interactions remain easy to answer;
- safe stop/resume remain reachable;
- raw diagnostics may use full-screen secondary pages.

---

# 50. Accessibility

## 50.1 Status

State must not be encoded only by color.

## 50.2 Keyboard

All primary interactions must be keyboard accessible.

Desktop file/Git navigation should have sensible focus order.

## 50.3 Focus management

After:

- submitting an interview answer;
- opening a modal;
- closing a modal;
- changing Project navigation;

focus should move predictably.

## 50.4 Live updates

Do not aggressively announce every Activity event to assistive technologies.

Announce only meaningful user-impacting changes, such as:

- needs input;
- Run stopped;
- Run failed;
- Run completed.

## 50.5 Contrast and text

Final visual design must meet appropriate accessibility contrast and readable sizing standards.

Exact design-system compliance is deferred to implementation/design-system work.

---

# 51. Content and Microcopy Rules

## 51.1 Prefer concrete verbs

Use:

- Start Run;
- Stop safely;
- Resume;
- Answer;
- Confirm intent;
- Download source;
- Open Preview.

Avoid vague:

- Proceed;
- Execute action;
- Continue process.

## 51.2 Explain engine behavior without engine jargon

Prefer:

```text
Kallula will continue from the existing workspace and checkpoint.
```

Not:

```text
--resume will reuse .pipeline-checkpoint.
```

## 51.3 Be explicit about uncertainty

Use:

```text
Stop outcome uncertain
```

instead of silently selecting a state.

## 51.4 Avoid anthropomorphic overstatement

The interface may say “Kallula is building” conversationally, but evidence surfaces should name the actual state.

Do not claim understanding or correctness beyond recorded evidence.

---


# 52. Security and Privacy UX Constraints

The underlying security mechanisms and credential-flow semantics are defined by [`Kallula — Security & Credentials Design.md`](./Kallula%20%E2%80%94%20Security%20%26%20Credentials%20Design.md).

The UI must preserve that design:

- browser authentication uses a Kallula session rather than exposing long-lived integration/provider credentials;
- no routine secret reveal exists after storage;
- secret inputs are blank on replace and never pre-populated with the stored value;
- platform/integration credentials and Project runtime credentials remain visually and semantically distinct;
- Project assignment means permission to use a named credential, not that agents automatically receive plaintext;
- Run snapshots display credential names/policy only;
- GitHub connection/publish UX never exposes App or installation tokens;
- Preview is treated as untrusted application content and never receives Kallula control-plane session cookies;
- logs/evidence may indicate redaction occurred but cannot offer an unredacted bypass;
- credential replace/delete flows identify affected Projects/runtimes where known;
- development-only insecure fallbacks must be visibly distinguishable from production-safe configuration;
- advanced diagnostics cannot bypass secret policy.

The UX must never imply that Kallula can recover/reveal a stored secret merely because it can use it internally.


# 53. Provenance UX

Kallula should progressively expose the chain from intent to result.

Initial surfaces should support links such as:

```text
Intent
  ↓
Specification
  ↓
Work Item
  ↓
Activity / consultation
  ↓
Tests
  ↓
Commit
  ↓
Review
  ↓
Verification
```

A dedicated graph-style Provenance Explorer is not required for the first release.

Instead, create contextual links:

- Work Item → commit;
- Work Item → test run;
- decision → related Work Item;
- verification → source commit;
- Verified State → verification evidence.

---

# 54. Primary User Journeys

## 54.1 New Project — interactive

```text
Dashboard
  ↓
Create Project
  ↓
Describe goal
  ↓
Choose "Interview me"
  ↓
Review factory defaults
  ↓
Create Project & begin interview
  ↓
Question appears
  ↓
Answer
  ↓
More questions
  ↓
Confirm final intent
  ↓
Autonomous Run begins
  ↓
Close browser
  ↓
Return later
  ↓
Current Run Overview reconstructs durable state
```

## 54.2 New Project — autonomous/defaulted

```text
Create Project
  ↓
Describe goal
  ↓
Choose "Use sensible defaults"
  ↓
Review configuration
  ↓
Create Project & start Run
  ↓
Run Overview
```

## 54.3 Leave during interview

```text
Question visible
  ↓
Close browser
  ↓
Run remains Needs your input
  ↓
Dashboard later shows attention card
  ↓
Open exact pending interaction
  ↓
Answer
  ↓
Same Run continues with a new Execution Attempt when required
```

## 54.4 Safe stop and resume

```text
Current Run
  ↓
Stop safely
  ↓
Confirm
  ↓
Stopping safely
  ↓
Engine reaches safe boundary
  ↓
Stopped
  ↓
Resume
  ↓
Compatibility confirmed
  ↓
New Execution Attempt
  ↓
Same Run continues
```

## 54.5 Failure with last Verified State

```text
Run fails
  ↓
Failure screen shows current unverified workspace
  + last Verified State
  ↓
Inspect evidence/logs
  ↓
Resume if supported OR retrieve source
```

## 54.6 Completion

```text
Run completes
  ↓
Verification outcome shown
  ↓
Verified State created when valid
  ↓
Result actions:
  Preview / Code / Download / Git / Publish
```

---

# 55. Screen-Level Mobile Priority Matrix

| View | Mobile priority |
|---|---|
| Dashboard | attention, active Runs, recent completion |
| Project Overview | current state, next action, Verified State |
| Pending Interaction | question, recommendation, answer actions |
| Run Overview | state, stage, Work Item, stop/resume, Verified State |
| Work Items | status list, blocker detail |
| Activity | chronological feed |
| Tests | verification summary first |
| Files | selected file, compact picker |
| Git | commits and verified marker |
| Preview | open full-screen |
| Logs | failure-linked segment first |
| Agents | profile + slot summary; advanced fields collapsible |
| Environment | Auto/proposed summary; advanced collapsible |
| Credentials | assignments and metadata |
| Knowledge | category list + detail |
| History | Run list + result |
| Engine/System | read-only diagnostics |

---

# 56. UX State Action Matrix

## 56.1 Run actions

| Run state | Primary user action |
|---|---|
| `QUEUED` | View status |
| `STARTING` | View status |
| `RUNNING` | Stop safely |
| `WAITING_FOR_HUMAN` | Answer now |
| `STOP_REQUESTED` | View stopping status |
| `STOPPED` | Resume if compatible |
| `FAILED` | Review failure; Resume only when supported |
| `COMPLETED` | Inspect results / start future work |

## 56.2 Preview actions

| Preview state | UX |
|---|---|
| Not runnable | Explain not yet available |
| Starting | Show startup state |
| Available | Open Preview |
| Unavailable | Explain temporary unavailability |
| Failed | Runtime Logs |
| Stopped | Explain stopped state; restart only if supported |

## 56.3 Verification actions

| Verification state | UX |
|---|---|
| Not run | Explain no verified state/current changes |
| Running | Show verification activity |
| Passed | Show exact Verified State |
| Failed | Show failed gate/evidence |
| Unknown/incompatible | Fail closed and explain |

---

# 57. Acceptance Criteria

## AC-UX-001 — Dashboard attention

A Project waiting for human input appears on the Dashboard without opening the Project and links directly to the pending interaction.

## AC-UX-002 — Browser return

Closing the browser on a pending question and reopening Kallula later restores the same unresolved question and accepted prior context.

## AC-UX-003 — No open-ended interview chat

The Phase 0 UX exposes typed question/answer/confirmation/delegation interactions, not a free-form arbitrary live-agent chat.

## AC-UX-004 — Run/stage separation

The Run Overview can simultaneously display `Needs your input` and stage `Requirements` without collapsing them into one status.

## AC-UX-005 — Stop truthfulness

After the user requests safe stop, the UI shows **Stopping safely** until backend/engine confirmation. It never immediately labels the Run `Stopped`.

## AC-UX-006 — Resume identity

Resuming a stopped Run clearly states that the same Run/workspace is continuing and that a new Execution Attempt may start.

## AC-UX-007 — Compatibility failure

When resume compatibility is not established, Resume is unavailable and the UI explains why without exposing a dangerous force-resume action.

## AC-UX-008 — Verified/current distinction

If current workspace changes after the last successful verification, Project Overview, Run Overview, Tests, Files, and Preview can all communicate that current state is not the Verified State.

## AC-UX-009 — Preview does not imply verification

A healthy Preview can be shown as available while the same screen still clearly states `Not yet verified`.

## AC-UX-010 — Mechanical evidence distinction

Model-authored success text cannot receive the same presentation as mechanically executed test/verification evidence.

## AC-UX-011 — Capability gating

An action unsupported by the pinned Engine Installation does not appear as a functioning button.

## AC-UX-012 — No native Siesta leakage

A normal user can operate Kallula without encountering `phase-3`, `.pipeline-checkpoint`, `stop.md`, or other current Siesta-native mechanics.

## AC-UX-013 — Agent capability rendering

The Agents page renders current engine Agent Slots and supported fields from capabilities rather than a permanently hard-coded schema.

## AC-UX-014 — Immutable historical configuration

Historical Run configuration is read-only and clearly distinguished from Project defaults.

## AC-UX-015 — Secret non-reveal

After credential creation, normal UI surfaces display metadata but provide no routine plaintext reveal action.

## AC-UX-016 — Fetch failure does not falsify Run failure

A frontend/API connectivity error is presented as a connectivity/data-loading problem and does not change the displayed Run state to `Failed`.

## AC-UX-017 — Mobile pending interaction

A pending question can be fully reviewed and answered on a narrow mobile browser without horizontal scrolling.

## AC-UX-018 — Mobile controls

Safe stop and Resume, when valid, remain reachable from mobile Run/Project surfaces.

## AC-UX-019 — Event reconnect

After live connection loss, the Activity view can show replayed durable history without presenting a gap caused solely by the connection interruption.

## AC-UX-020 — Attempt visibility

Run History can show multiple Execution Attempts under one logical Run without representing them as separate Runs.

## AC-UX-021 — No false progress

Before Work Items exist, the UI uses stage state and does not fabricate a completion percentage.

## AC-UX-022 — Source read-only during execution

During active autonomous execution, the Files view contains no editing controls.

## AC-UX-023 — Failure context

A failed Run provides failed stage, Work Item when known, reason/evidence links, current workspace trust state, and last Verified State when one exists.

## AC-UX-024 — Deep-link restoration

A notification/deep link to a pending interaction or failed Run resolves to the correct durable Project/Run state after authentication.

## AC-UX-025 — Accessibility

Core statuses and actions remain understandable without color and are operable by keyboard.

---

# 58. PRD Traceability

| PRD area | UX resolution |
|---|---|
| §6 Foundational principles | §§4, 11–14, 51–53 |
| §9 Core domain model | §§6, 20–45 |
| §10 Product state model | §§7, 11–14, 41–43 |
| KAL-FR-010–013 Dashboard | §§16–17 |
| KAL-FR-020–025 Project creation | §18 |
| KAL-FR-030–034 Repository import | §19 |
| KAL-FR-040–046 Human interaction | §22 |
| KAL-FR-050–053 Start/execution | §§18, 23 |
| KAL-FR-060–063 Run monitoring | §§23, 14 |
| KAL-FR-070–073 Events | §25 |
| KAL-FR-080–083 Safe stop | §41 |
| KAL-FR-090–093 Resume | §42 |
| KAL-FR-100–102 Failure | §43 |
| KAL-FR-110–112 Work Items | §24 |
| KAL-FR-120–123 Tests/verification | §26 |
| KAL-FR-130–133 Files | §27 |
| KAL-FR-140–143 Source export | §§21, 54 |
| KAL-FR-150 Git | §28 |
| KAL-FR-160–164 GitHub | §§28, 39 |
| KAL-FR-170–175 Preview | §29 |
| KAL-FR-180–182 Runtime logs | §30 |
| KAL-FR-190–194 Environment | §32 |
| KAL-FR-200–205 Agents | §31 |
| KAL-FR-210–212 Profiles | §37 |
| KAL-FR-220–224 Skills | §§31, 37 |
| KAL-FR-230–236 Credentials | §§33, 38 |
| KAL-FR-240–243 Credential isolation | §§33, 52 |
| KAL-FR-250–252 Knowledge | §34 |
| KAL-FR-260 Provenance | §53 |
| KAL-FR-270–271 Verified/current | §12 |
| KAL-FR-280–281 Run history | §35 |
| KAL-FR-290 Engineering preferences | §36 |
| KAL-FR-300 Notifications | §§7, 45 |
| §13–15 Frontend architecture/views/behavior | §§8–14, 16–55 |
| §26 Usability/accessibility | §§49–51 |
| §29 Product invariants | §§41–43, 57 |

---

# 59. Architecture Traceability

| Architecture area | UX consequence |
|---|---|
| §§9–12 Project/Run/Attempt model | Project shell, Run History, attempt detail |
| §13 Run state machine | normalized user-visible states/actions |
| §15 Stage model | capability-driven stage rail |
| §17 Human Interaction | durable typed Pending Interaction UX |
| §18 Safe Stop | `Stopping safely` intermediate state |
| §19 Resume/Recovery | same-Run continuation UX |
| §20 Execution ownership | no concurrent conflicting start/resume actions |
| §§22–25 Events/artifacts/verified state | Activity, Files, Tests, Verified State |
| §28 interaction flow | answer idempotency and deep-link restoration |
| §§29–30 stop/resume flows | §§41–42 |
| §§32–33 failure/reconciliation | §43 |
| §§35–39 engine evolution | capability/compatibility UX |
| §41 live updates | §14 |
| §42 trust boundaries | credential/log/preview UX constraints |
| §49 invariants | UX truth rules and acceptance criteria |

---

# 60. Siesta Adaptation Traceability

| Adaptation area | UX consequence |
|---|---|
| §§12–14 durable interactions | §22 |
| §§15–18 events/stages/work items | §§11, 23–25 |
| §19 artifacts | Files, tests, diagnostics links |
| §20 semantic outcome | completion/failure truth |
| §21 safe stop | §41 |
| §22 resume | §42 |
| §§23–25 state/compatibility | §§40, 42–43 |
| §§26–28 Agent Slots/configuration | §§31, 37 |
| §§29–30 learning isolation | read-only Run snapshots / profile versioning |
| §31 environment isolation | credential exposure language |
| §34 verification mapping | §§12, 26 |
| §35 failure classification | §43 |
| §36 idempotency | answer/action submission behavior |
| §§37–38 capabilities | capability-driven control rendering |
| §§42–45 upgrade/compatibility | Engine & System / resume warnings |
| §46 raw evidence | diagnostics links |

---

# 61. Deliberately Open UX/Design Decisions

This specification fixes behavior and information hierarchy. The following remain open:

1. final brand identity;
2. color palette;
3. typography;
4. iconography;
5. exact component library;
6. exact desktop sidebar/tab visual composition;
7. exact responsive pixel breakpoints;
8. embedded versus new-window Preview presentation;
9. whether command palette/global search is included in v1;
10. exact notification delivery channels;
11. exact Git diff viewer implementation;
12. exact syntax highlighting/editor viewer library;
13. exact visual design for Provenance relationships;
14. whether Engine & System diagnostics are hidden behind an “Advanced” toggle or a dedicated settings item;
15. exact copy for authentication/provider-specific connection flows;
16. final visual copy/details of GitHub repository permission and publish/PR flows within the now-defined GitHub App security model;
17. exact visual controls for the now-defined Environment Profile/Runtime Plan fields;
18. exact credential provider/category validation copy after concrete provider integrations are selected.

These are not reasons to defer the behavioral flows defined by this document.

---


# 62. Implementation Status

The implementation plan now exists:

> [`Kallula — Implementation Plan.md`](./Kallula%20%E2%80%94%20Implementation%20Plan.md)

Use that document to sequence development and select the first-release implementation choices.

No more architecture document is required before coding starts.

The **Test & Compatibility Strategy** is still required before release. It is intentionally deferred until the implementation has real testable seams, runtime behavior, and compatibility fixtures.


# Appendix A — Primary Screen Inventory

## Global

1. Authentication
2. Dashboard
3. Projects
4. Create Project
5. Agent Profiles
6. Global Credentials
7. Integrations
8. Engine & System
9. Application settings

## Project

10. Project Overview
11. Pending Interaction / Interview
12. Current Run Overview
13. Work Items
14. Activity
15. Tests & Verification
16. Files
17. Git
18. Preview
19. Runtime Logs
20. Agents
21. Environment
22. Project Credentials
23. Knowledge
24. Run History
25. Project Settings

## Secondary/detail surfaces

26. Run configuration snapshot
27. Execution Attempt detail
28. Event detail
29. Work Item detail
30. Test/verification detail
31. Commit detail
32. Engine compatibility detail
33. Raw engine evidence/log detail
34. Credential create/replace/delete dialogs
35. Safe-stop confirmation
36. Resume confirmation
37. Delegate-remaining-interview confirmation

---

# Appendix B — Primary Status Vocabulary

## Run

| Backend state | Primary label |
|---|---|
| `QUEUED` | Queued |
| `STARTING` | Starting |
| `RUNNING` | Running |
| `WAITING_FOR_HUMAN` | Needs your input |
| `STOP_REQUESTED` | Stopping safely |
| `STOPPED` | Stopped |
| `FAILED` | Failed |
| `COMPLETED` | Completed |

## Verification

| State | Label |
|---|---|
| no verified result | No verified state yet |
| current state differs | Current workspace not yet verified |
| passed | Verified |
| failed | Verification failed |
| compatibility unknown | Verification state unavailable |

## Preview

| State | Label |
|---|---|
| not runnable | Not runnable |
| starting | Starting |
| available | Available |
| unavailable | Unavailable |
| failed | Failed |
| stopped | Stopped |

---

# Appendix C — Primary Action Vocabulary

Use consistently:

- Create Project
- Begin interview
- Start Run
- Answer
- Confirm intent
- Request a change
- Use the recommendation
- Let Kallula decide the remaining questions
- Stop safely
- Request safe stop
- Resume
- Open Preview
- View source
- Download source
- View Git
- View evidence
- Runtime logs
- Publish
- Assign credential
- Replace credential
- Delete credential

Avoid using different labels for the same semantic action on different screens.

---

# Appendix D — UX Invariants

1. A screen may simplify presentation but may not simplify backend truth.
2. Current source and Verified State are always distinguishable when they differ.
3. Preview health never proves verification.
4. Model narration never substitutes for mechanical evidence.
5. Run state and engine Stage remain independent.
6. Execution Attempt identity never replaces Run identity.
7. Pending interactions are durable objects, not transient chat bubbles.
8. A submitted interaction answer cannot be casually edited after acceptance.
9. `STOP_REQUESTED` remains visible until stop is confirmed or reconciled otherwise.
10. Resume never implies recreation from the original prompt.
11. Unsupported engine capabilities never appear as functioning controls.
12. Historical Run configuration is immutable in the UI.
13. Normal UX does not expose Siesta-native checkpoint/stop/phase mechanics.
14. Secret values do not have a normal reveal path after storage.
15. Connectivity loss is not Run failure.
16. Loading state is not engine activity state.
17. Mobile preserves operating actions even when dense diagnostics are simplified.
18. Accessibility information is part of the state model, not an optional decoration.

---

# Final UX Rule

> **At every moment, Kallula should let the user understand what needs attention, what the autonomous system is doing, what evidence exists, what is currently safe to trust, and what actions are actually valid—without requiring knowledge of Siesta's internal mechanics.**
