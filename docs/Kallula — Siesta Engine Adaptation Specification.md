# Kallula — Siesta Engine Adaptation Specification

**Document status:** Normative engine-integration specification — pre-implementation
**Product:** Kallula
**Primary product specification:** [`Kallula — Product Requirements Document.md`](./Kallula%20%E2%80%94%20Product%20Requirements%20Document.md)
**Parent architecture:** [`Kallula — System Architecture & State Model.md`](./Kallula%20%E2%80%94%20System%20Architecture%20%26%20State%20Model.md)
**Normative UX & interaction specification:** [`Kallula — UX & Interaction Specification.md`](./Kallula%20%E2%80%94%20UX%20%26%20Interaction%20Specification.md)
**Normative security & credentials design:** [`Kallula — Security & Credentials Design.md`](./Kallula%20%E2%80%94%20Security%20%26%20Credentials%20Design.md)
**Normative execution environment & Preview design:** [`Kallula — Execution Environment & Preview Design.md`](./Kallula%20%E2%80%94%20Execution%20Environment%20%26%20Preview%20Design.md)
**Normative API & data contract specification:** [`Kallula — API & Data Contract Specification.md`](./Kallula%20%E2%80%94%20API%20%26%20Data%20Contract%20Specification.md)
**Initial execution engine:** Siesta (`jairorodriguezarias/siesta`)
**Siesta repository baseline reviewed:** `main`, tree/commit snapshot `20b149e0734b09730dfd22803d2695776fcf84b8`
**Implementation plan:** [`Kallula — Implementation Plan.md`](./Kallula%20%E2%80%94%20Implementation%20Plan.md)  
**Implementation status:** Not started
**Purpose:** Define exactly how Kallula integrates with, adapts, constrains, observes, configures, suspends, resumes, and upgrades the current Siesta engine while preventing Siesta-native implementation details from leaking throughout the rest of Kallula.
**Audience:** Engine-integration, backend/control-plane, runner, security, QA, infrastructure, and future Siesta-upgrade maintainers.

> **Normative relationship:** The PRD defines required product behavior. The **System Architecture & State Model** defines Kallula's system boundaries, ownership, lifecycle, and state semantics. This document is authoritative only for the **Siesta-specific adaptation boundary**: the engine-facing contract, required narrow Siesta changes, current native-to-normalized mappings, capability declaration, compatibility validation, and upstream-update process. The **UX & Interaction Specification** consumes the normalized semantics defined here and is authoritative for browser presentation and interaction behavior, but must not override engine truth or capability constraints. The **Security & Credentials Design** is authoritative for credential domains, child-environment security, provider/GitHub authority, runtime-secret policy, redaction, and Preview trust constraints that this adapter must respect. The **Execution Environment & Preview Design** is authoritative for how the adapter is physically hosted: immutable Engine Installation mount, canonical Workspace mount, Run Engine Runtime mount, worker isolation/resources/network, Attempt teardown/recreation, and the separation between coding worker and generated-application Preview. The **API & Data Contract Specification** defines the durable Run/Attempt/Interaction/Work Item/Event/Artifact records into which this adapter is normalized, including `(attempt_id, source_event_sequence)` ingestion idempotency and Run-local Event sequence allocation. If this document conflicts with the PRD or System Architecture & State Model, the higher-level document takes precedence until the documents are deliberately reconciled.

> **Design rule:** Kallula must adapt Siesta; it must not fork Siesta's product semantics into the rest of the platform. Siesta-native phase names, filenames, prompt markers, role names, checkpoint files, stop files, and Python modules may be understood by the adapter. They must not become general Kallula domain contracts.

> **Baseline rule:** Statements about “current Siesta” in this document refer specifically to the reviewed repository snapshot above. A later upstream revision is not assumed to behave identically until the compatibility process in this document has validated it.

---

# 1. Purpose

Kallula uses Siesta as its initial autonomous software-development engine.

The PRD and architecture deliberately prevent the rest of Kallula from depending directly on today's Siesta implementation. This document turns that principle into an actionable integration design.

It answers:

- How does Kallula launch a pinned Siesta revision against an exact Project workspace?
- How does Siesta request human input without reading from a live terminal?
- How can that human interaction survive browser and worker absence?
- How are Siesta phases, issues, tests, review, verification, learning, and Git activity converted into normalized Kallula events?
- How does Kallula request a safe stop without exposing `stop.md` as a product API?
- How does a resumed Execution Attempt continue native Siesta state without reconstructing it from Kallula projections?
- Which current Siesta files are authoritative artifacts, which are diagnostics, and which are private engine bookkeeping?
- How are Planner, Worker, and Consultant represented as capability-driven Agent Slots?
- How are per-Run model and skill configurations supplied without mutating a shared engine installation?
- How are self-learning skill changes isolated so one Run cannot silently change another Run?
- How is the Pi child-process environment prevented from inheriting Kallula secrets?
- What exact evidence is required before a new upstream Siesta revision is marked supported?

This specification intentionally solves the integration seam before final REST endpoints, database tables, worker container technology, or frontend component design are fixed.

---

# 2. Scope and Authority

This document is authoritative for:

1. the Kallula-to-Siesta process/programming boundary;
2. the minimum generic changes Kallula requires in Siesta;
3. the external workspace contract;
4. durable human-interaction adaptation;
5. native event emission and normalization responsibilities;
6. safe-stop translation;
7. resume and checkpoint inspection;
8. native state-format identification;
9. stage/work-item/artifact mappings for the reviewed Siesta baseline;
10. Agent Slot and engine configuration capability mapping;
11. Run-scoped engine assets and learning isolation;
12. child-process environment filtering requirements;
13. structured terminal-result translation;
14. raw diagnostic capture;
15. capability-manifest requirements;
16. Engine Installation identity and compatibility validation;
17. the upstream update/rebase workflow;
18. engine-integration acceptance criteria.

This document is **not** authoritative for:

- Kallula Project/Run lifecycle semantics already defined by the architecture;
- final Kallula persistence tables;
- public REST/GraphQL/WebSocket/SSE endpoints;
- exact command queue technology;
- exact worker sandbox/container/VM technology;
- encryption/key-management implementation;
- final browser UX/layout;
- GitHub authentication;
- production preview routing;
- billing, organization RBAC, or distributed scaling.

---

# 3. Integration Goals

The adaptation must satisfy the following goals.

## 3.1 Preserve Siesta's reliability model

Kallula must not weaken Siesta's mechanical gates.

Tests, review, verification, issue completion, recovery archives, Git commits, and checkpoint semantics remain engine-owned behaviors unless a deliberate future engine change says otherwise.

## 3.2 Keep changes narrow and upstream-friendly

The preferred shape is:

```text
Upstream Siesta
    +
small generic integration seams
    +
Kallula-owned adapter
```

not:

```text
Copy Siesta into Kallula
    +
rewrite its pipeline around Kallula
```

Generic seams should be useful outside Kallula where practical: explicit workspace selection, programmatic execution, human-interaction hooks, event hooks, structured outcomes, and explicit child environments are all reasonable engine capabilities in their own right.

## 3.3 Preserve standalone Siesta usage

The current CLI experience should continue to work after the adaptation.

A developer should still be able to run Siesta directly from a terminal without Kallula. The CLI may internally delegate to the new programmatic execution entrypoint.

## 3.4 Make the integration replaceable

No Kallula component outside the adapter boundary should need to import Siesta modules or parse Siesta files to perform ordinary product logic.

## 3.5 Make engine upgrades explicit

A new Siesta revision becomes a Kallula Engine Installation only after introspection and compatibility testing. Pulling a new Git commit is not itself an upgrade.

---

# 4. Non-Goals

The first adaptation is not intended to:

- generalize Kallula into a marketplace for arbitrary coding engines;
- rewrite Siesta as a network service;
- replace Pi;
- replace Siesta's KB with a Kallula database;
- replace Siesta's Git workflow;
- make every internal prompt user-editable;
- parallelize Siesta issue execution;
- implement live browser source editing;
- expose arbitrary project secrets to agents;
- redesign Siesta's planning, execution, review, verification, or recovery algorithms;
- provide cross-project autonomous shared-skill mutation in the initial hosted product;
- infer support for capabilities that the adapter has not explicitly declared and tested.

---

# 5. Current Siesta Baseline — Observed Behavior

The reviewed repository currently has a small Python orchestrator under `factory/pipeline/` and invokes Pi as its coding-agent process.

The relevant baseline behavior is summarized below because the adaptation must be grounded in real current behavior rather than a hypothetical engine.

## 5.1 Entry point

Current execution enters through:

```text
python3 -m pipeline "<idea>" [--auto] [--resume]
```

The shell wrapper `factory/bin/siesta.sh` ultimately invokes the Python pipeline.

`factory/pipeline/__main__.py` owns:

- argument parsing;
- project-path selection;
- pipeline checkpoint progression;
- phase dispatch;
- failure learning;
- final result handling;
- project-level learning;
- terminal summary output.

## 5.2 Current project location

Without adaptation, Siesta derives a slug from the idea and stores generated projects under a factory-controlled `projects/<slug>` directory.

That is unsuitable as Kallula's Project identity/storage contract because Kallula already owns the canonical Project workspace and uses stable internal IDs independent of display names or slugs.

## 5.3 Current native checkpoint

Current Siesta persists `.pipeline-checkpoint` and recognizes:

```text
phase-0
phase-1
phase-2
phase-3
phase-4
phase-5
complete
```

The checkpoint is monotonic in normal progression, but the engine may deliberately move it backwards when pending work or failed verification requires re-execution.

Checkpoint alone does not fully define completion. Current resume logic also consults:

- the issue plan;
- project KB completion/blocker nodes;
- `verify_verdict.txt`;
- Git/project state.

## 5.4 Current pipeline responsibilities

The reviewed baseline uses these broad native stages:

```text
Phase 0  Interview / intent
Phase 1  Specification
Phase 2  Planning
Phase 3  Issue execution + per-issue learning
Phase 4  Review
Phase 5  Verification
Phase 6  Completion recording
Phase 7  Project-level learning
```

Only `phase-0` through `phase-5` and `complete` are persisted in the current checkpoint file.

## 5.5 Current human interaction

The interactive Phase 0 loop currently obtains answers through:

```python
input("> ")
```

The transcript is written to `interview_output.txt` as the dialog progresses.

The final intent requires explicit human confirmation in interactive mode unless the user delegates the remaining decisions through the existing `auto` behavior.

This terminal dependency is the most important behavior that must change for hosted Kallula operation.

## 5.6 Current safe stop

Current Siesta checks for `stop.md` at issue boundaries during execution.

When the marker is detected, Siesta records a blocker and halts cleanly. A clean exit status therefore does **not** mean “project completed successfully.”

## 5.7 Current resume behavior

Existing project state is automatically recognized from the workspace. Pending issues can invalidate downstream review/verification checkpoints. Failed verification can cause verification to be retried rather than falsely reusing a pass.

This is exactly why Kallula must resume native engine state rather than reconstructing progress from UI records.

## 5.8 Current roles

Current `factory/config/models.json` defines three explicit routes:

- Planner;
- Worker;
- Consultant.

Reviewer behavior reuses Worker; proxy and learner behavior reuse Consultant according to current orchestration.

## 5.9 Current model invocation

`factory/pipeline/pi.py` is the central Pi invocation wrapper.

It:

- builds Pi arguments;
- supplies model/provider;
- supplies skills;
- selects thinking mode;
- runs Pi as a subprocess;
- applies a timeout;
- captures stdout and provider stderr separately;
- optionally persists raw artifacts.

## 5.10 Current child environment

The current `_child_env()` starts from the entire Siesta process environment and adds `PYTHONPATH`.

That is safe enough for a local developer process but is not an acceptable hosted secret boundary.

## 5.11 Current knowledge stores

Current Siesta maintains:

- a Project KB under the generated project;
- a factory-level global KB;
- factory skills that the learner may update.

The JSON Graph implementation uses atomic file replacement for writes but does not provide concurrent-writer coordination.

## 5.12 Current learning mutation

The current learner may rewrite/create selected `factory/skills/*/SKILL.md` files.

In a shared hosted installation, allowing every Run to mutate one common skill directory would destroy reproducibility and introduce cross-Run races.

## 5.13 Current verification truthfulness

Current verification combines model output with mechanical tests and applicable runtime checks. A model saying `VERIFY_PASSED` cannot override failing or missing required mechanical evidence.

Kallula must preserve this relationship.

---

# 6. Adaptation Architecture

```text
Kallula product contracts
          |
          v
+-------------------------+
| Kallula Siesta Adapter  |
+-------------------------+
          |
          v
+-------------------------+
| Siesta engine           |
+-------------------------+
          |
          v
Native Siesta details
(phases, files, markers, checkpoints)

Only the adapter knows both sides.
```


The integration boundary is:

```text
Kallula Control Plane
        │
        │ durable command / persisted state
        ▼
Kallula Run Coordinator
        │
        ▼
Execution Worker
        │
        ├── Kallula Siesta Adapter Runtime
        │       │
        │       ├── stable Kallula-facing adapter contract
        │       │
        │       └── Siesta-specific translation
        │
        └── Pinned Siesta Engine
                │
                ├── narrow generic integration hooks
                ├── Pi
                └── generated-project tooling
        │
        ▼
Canonical Project Workspace
```

## 6.1 Process boundary

The **Kallula Siesta Adapter Runtime** runs inside the Execution Worker boundary.

The Control Plane and general Run services do not import Siesta.

The adapter may import the pinned Siesta Python integration API **inside the worker process**. This is preferred over having general Kallula application code import `pipeline.phases`, `pipeline.pi`, or other internal modules directly.

The adapter and Siesta may initially execute in one worker process. They do not need to become separate network services.

## 6.2 Stable external boundary

The Coordinator interacts with a Kallula engine-runner contract. It should not know whether current Siesta internally uses Python calls, files, Pi, or Git commands.

The exact transport between Coordinator and Worker is delegated to later API/execution design. The semantics in this document are fixed regardless of transport.

## 6.3 Siesta integration boundary

Within the worker, the adapter uses one documented Siesta programmatic entrypoint and documented hooks.

It must not reach arbitrarily into multiple private functions as the primary integration method.

Tests may inspect internals where necessary, but production integration must have a narrow supported seam.

---

# 7. Required Siesta Integration Surface

The Kallula-compatible Siesta build must expose behavior equivalent to the following conceptual operations.

Names below are illustrative; semantics are normative.

```text
inspect_engine()
run(request, hooks) -> engine_outcome
inspect_workspace(workspace) -> native_state
inspect_resume_compatibility(workspace, engine_identity) -> compatibility
request_safe_stop(workspace or active_execution)
discover_artifacts(workspace) -> native_artifacts
```

`run()` must support both first execution and continuation against an existing workspace.

The CLI may call the same underlying execution function with terminal/default hooks.

**KSA-REQ-001** — Kallula production integration must use a documented Siesta integration surface rather than importing arbitrary private phase functions throughout the adapter.

**KSA-REQ-002** — Standalone Siesta CLI behavior must remain available after the integration surface is introduced.

**KSA-REQ-003** — The integration surface must accept an explicit canonical workspace supplied by Kallula.

**KSA-REQ-004** — The integration surface must return a structured semantic outcome rather than forcing Kallula to infer the result solely from process exit status.

---

# 8. Minimal Upstream Siesta Change Strategy

Kallula should maintain the smallest practical patch surface against upstream Siesta.

The required change categories are:

1. programmatic execution entrypoint;
2. explicit workspace injection;
3. external/durable human-interaction hook;
4. structured event hook;
5. structured terminal outcome;
6. explicit/sanitized child environment input;
7. native state-format/capability metadata;
8. restartable Phase 0 interaction state.

Everything else should remain in Kallula's adapter where possible.

Examples of logic that should **not** be moved into Siesta merely for Kallula:

- authentication;
- Project ownership;
- Kallula Run state;
- Execution Attempt records;
- browser notification;
- GitHub OAuth/App integration;
- preview routing;
- credential encryption;
- Kallula event storage;
- Kallula database access.

**KSA-REQ-010** — Siesta integration code must not import or depend on Kallula's database models, web framework, authentication model, or UI concepts.

**KSA-REQ-011** — Generic hooks should be implemented without hard-coding Kallula service URLs or credentials into upstream Siesta.

---

# 9. Engine Installation Layout

A Kallula Engine Installation represents an immutable tested engine package, not a mutable live factory directory.

Conceptually it contains:

```text
Engine Installation
├── upstream Siesta source/revision
├── Kallula-required generic patch set, if not upstreamed
├── immutable adapted skills
├── immutable baseline factory skills
├── KB schema + global seed
├── default/reference model config
├── adapter compatibility metadata
└── compatibility-suite result
```

Mutable execution state must not be written back into the Engine Installation.

**KSA-REQ-020** — A supported Engine Installation must be immutable after registration.

**KSA-REQ-021** — Mutable factory skill content, global learning data, project state, and run diagnostics must live outside the immutable installation.

**KSA-REQ-022** — The installation identity must include or reference the exact upstream revision and exact Kallula patch/adaptation revision.

---

# 10. Run-Scoped Siesta Runtime Assets

Current Siesta expects a factory root containing configuration, factory skills, and global KB material. Kallula must provide this without creating shared mutable state between Runs.

For the initial hosted design, each logical Run receives a **Run Engine Runtime** derived from its pinned Engine Installation.

Conceptually:

```text
Run Engine Runtime
├── config/
│   └── models.json          ← materialized from immutable Run config snapshot
├── skills/                  ← writable Run-scoped factory skill copy
├── kb/
│   ├── schema.json
│   ├── global-seed.json
│   └── global-graph.json    ← Run-scoped learning context
└── adapter metadata
```

The canonical generated Project workspace remains separate.

The current `SIESTA_FACTORY` mechanism may be used internally by the adapter to point Siesta at this Run-scoped runtime, but `SIESTA_FACTORY` is not a Kallula domain concept.

## 10.1 Why Run-scoped instead of shared

This isolates:

- learner skill updates;
- model configuration;
- factory/global learning state;
- mutable engine runtime artifacts.

It also makes resumed Execution Attempts within the same Run see the same evolved engine assets while preventing an unrelated Run from silently changing them.

## 10.2 Cross-project learning policy

The initial Kallula adaptation does **not** automatically merge Run-generated global KB changes or learned skill changes into a shared global engine installation.

Such changes remain attributable to the Run that produced them.

Promotion into a future shared learning profile may be designed later as an explicit reviewed/versioned operation.

This intentionally trades automatic cross-project self-modification for reproducibility and isolation in the first hosted product.

**KSA-REQ-030** — Every Run must receive an isolated mutable Siesta runtime area.

**KSA-REQ-031** — Resumed Attempts for the same Run must reuse that Run's persisted engine-runtime state unless a validated migration explicitly says otherwise.

**KSA-REQ-032** — Two Runs must not write the same mutable factory-skill directory concurrently.

**KSA-REQ-033** — Automatic learner changes from one Run must not alter another active or historical Run's effective configuration.

---

# 11. External Canonical Workspace Injection

Kallula owns the canonical Project workspace identity and location.

Siesta must support an explicitly supplied Project directory.

When the workspace is supplied externally:

- Siesta must use that exact directory;
- Siesta must not derive another workspace from the idea slug;
- Siesta must not silently redirect to `factory/projects/<slug>`;
- all source, tests, project KB, Git, checkpoint, verification evidence, and recovery artifacts must be created/read in that workspace according to native Siesta behavior;
- the user-facing Project name may differ from the filesystem identifier.

The existing slug-based behavior remains valid for standalone CLI usage when no external workspace is supplied.

**KSA-REQ-040** — Kallula mode must provide an explicit canonical workspace path to Siesta.

**KSA-REQ-041** — In Kallula mode, workspace selection must not depend on prompt text or slug uniqueness.

**KSA-REQ-042** — Siesta must never create a second generated-project copy outside the canonical Kallula workspace during ordinary execution.

**KSA-REQ-043** — Workspace injection must support resume against the same path across different Execution Attempts.

---

# 12. Human Interaction Adaptation

Replacing terminal `input()` with a browser RPC is insufficient.

Kallula requires human interaction to be:

- durable;
- correlated;
- restartable;
- independent of browser connection;
- safe when the worker process is released or lost;
- exactly-once at the Kallula interaction state level.

The adapted Siesta interview therefore uses a generic **Human Interaction Channel** rather than directly reading stdin.

## 12.1 Two channel implementations

The engine should support at least two implementations:

### Terminal channel

Used by standalone Siesta.

It preserves the current terminal behavior.

### External channel

Used by Kallula.

It does not talk to a browser directly. It exposes a human-input request to the adapter and permits execution to cooperatively suspend.

## 12.2 Cooperative suspension

When Siesta reaches a human answer point in Kallula mode:

```text
Siesta creates native interaction request
        ↓
Native pending-interaction state is persisted
        ↓
Engine event/hook exposes the request to adapter
        ↓
Adapter returns WAITING_FOR_HUMAN outcome
        ↓
Execution Attempt ends cleanly
        ↓
Kallula keeps durable Pending Interaction
```

The worker does **not** need to remain alive for hours waiting for a person.

When the user answers:

```text
Kallula accepts answer once
        ↓
Run is queued/resumed
        ↓
new Execution Attempt starts
        ↓
Adapter supplies accepted response keyed to native interaction ID
        ↓
Siesta loads pending interview state
        ↓
answer is applied once
        ↓
interview continues
```

The architecture already allows `WAITING_FOR_HUMAN → QUEUED/RUNNING` according to the continuation model; this document chooses **new Execution Attempt after durable suspension** for Kallula's initial Siesta integration.

**KSA-REQ-050** — Kallula's Siesta integration must not require an Execution Worker to remain alive while waiting indefinitely for human input.

**KSA-REQ-051** — A human-input request must have a stable native correlation identity before the worker suspends.

**KSA-REQ-052** — Siesta must persist enough native Phase 0 state to continue after process restart without discarding prior accepted interview turns.

**KSA-REQ-053** — The accepted answer must be applied only to the matching pending native interaction.

**KSA-REQ-054** — Replaying an already-consumed answer must not duplicate a transcript turn or advance the interview twice.

---

# 13. Durable Interview State

Current `interview_output.txt` is useful evidence but is not, by itself, a sufficiently explicit restart protocol for a browser-mediated suspended interaction.

The adapted engine must maintain engine-native pending-interaction state in the workspace.

The exact file name is native and intentionally hidden from Kallula. Conceptually the state records:

- interaction state format version;
- stable native interaction ID;
- interaction kind;
- interview turn number;
- prompt/question presented to the user;
- recommendation/guess when present;
- whether this is final-intent confirmation;
- relevant transcript position/hash;
- creation timestamp where available;
- whether the response has been consumed.

The user-visible transcript remains engine evidence.

## 13.1 Restart rule

On Phase 0 restart, Siesta must first inspect native pending-interaction state.

If a pending interaction exists:

- it must not ask the model for a new replacement question first;
- it must request/consume the response for the existing interaction;
- the resulting transcript update must be persisted before generating the next model turn.

This prevents a worker crash/restart from changing the question the human was asked.

## 13.2 Final intent confirmation

The same durable mechanism applies to the final intent confirmation.

The final summary must be recoverable as the exact pending interaction instead of existing only in process memory while waiting for `yes` or refinement text.

**KSA-REQ-060** — Pending question state must be persisted before Kallula is told that the Run is waiting for human input.

**KSA-REQ-061** — Final intent confirmation must use the same durable interaction mechanism as ordinary interview questions.

**KSA-REQ-062** — A restarted engine must resume the existing pending interaction before generating another model turn.

---

# 14. Interaction Types Exposed to Kallula

The baseline adapter normalizes at least these interaction purposes:

| Kallula interaction purpose | Current Siesta origin | User response semantics |
|---|---|---|
| `requirements_question` | Phase 0 `Q:` / `GUESS:` | free-text answer or explicit delegation |
| `intent_confirmation` | Phase 0 `INTENT_FINALIZED:` | accept or refinement text |

Current post-Phase-0 execution remains autonomous in the first release.

Consultant/proxy actions are internal autonomous engine interactions and are **events/evidence**, not browser human interactions.

Future Kallula steering must not reuse these Phase 0 interaction types as an uncontrolled chat channel.

---

# 15. Structured Engine Event Hook

Console text is diagnostic evidence, not a sufficient product event contract.

The Kallula-compatible Siesta build must expose a lightweight structured event hook.

The event hook is best-effort from the engine's perspective but must be emitted at authoritative transition points in the code, not reconstructed solely from terminal log strings.

The adapter receives native engine events and converts them into normalized Kallula events.

## 15.1 Event design principle

Native events describe **what Siesta did**.

Kallula events describe **what the product can assert**.

The adapter may enrich a native event with:

- Project/Run/Attempt identity;
- normalized Stage identity;
- normalized Work Item identity;
- engine/adapter version;
- artifact references;
- Kallula Run-local sequence assigned at persistence time.

## 15.2 Engine event payload minimum

A native event should carry:

- event kind;
- native timestamp if available;
- native stage/phase identity;
- work-item number/identity where relevant;
- human-readable summary;
- structured outcome fields where relevant;
- native correlation ID;
- artifact/evidence references when applicable.

The exact Kallula persistence schema belongs in the API/Data Contract Specification.

**KSA-REQ-070** — Significant engine transitions must have structured hooks at the source of the transition.

**KSA-REQ-071** — Kallula must not parse ANSI console output as its primary mechanism for determining stage completion, verification success, or safe stop.

**KSA-REQ-072** — Native events may be duplicated across retries/recovery; the adapter/control plane must have correlation information sufficient for idempotent normalization.

---

# 16. Baseline Native Event Coverage

The adapted baseline should emit events equivalent to the following.

## 16.1 Engine lifecycle

- engine invocation started;
- engine resumed existing workspace;
- engine waiting for human;
- engine safe-stopped;
- engine completed;
- engine incomplete/unverified;
- engine failed.

## 16.2 Stage lifecycle

- native phase started;
- native phase completed;
- phase invalidated/reopened when current Siesta rewinds checkpoint state.

## 16.3 Work-item lifecycle

- issue started;
- issue skipped because already completed;
- issue blocked;
- issue completed;
- issue recovery/cleanup performed.

## 16.4 Consultation/proxy

- consultation requested;
- consultation completed;
- proxy approval requested;
- proxy approved/rejected/revision required;
- deep diagnosis/escalation.

## 16.5 Test/recovery

- regression suite started;
- regression suite result;
- repair attempt started;
- repair result;
- repair commit result.

## 16.6 Review and verification

- review started;
- review result;
- review repair started/completed;
- verification started;
- mechanical tests result;
- runtime smoke-check result where applicable;
- final verification verdict.

## 16.7 Git/evidence

- commit created or commit failed;
- recovery archive created;
- important artifact finalized.

## 16.8 Learning

- per-issue learning started/completed;
- project learning started/completed;
- factory skill update proposed/applied within Run scope.

This does not need an event for every log line or file write.

---

# 17. Native Stage Normalization

Kallula uses stable normalized stages while allowing Siesta's native topology to evolve.

For the reviewed baseline, the mapping is:

| Native Siesta state | Normalized Kallula stage | Notes |
|---|---|---|
| `phase-0` / Phase 0 | `requirements` | interactive intent clarification/finalization |
| `phase-1` / Phase 1 | `specification` | `spec.md` generation |
| `phase-2` / Phase 2 | `planning` | `issues.md` generation |
| `phase-3` / Phase 3 | `execution` | issue loop, recovery, per-issue learning |
| `phase-4` / Phase 4 | `review` | code review and repair loop |
| `phase-5` / Phase 5 | `verification` | tests/runtime verification |
| Phase 6 | `completion` | result recording/commit; not independently checkpointed |
| Phase 7 | `learning` | project-level learning; `complete` is only persisted after successful learning path |
| `complete` | terminal engine checkpoint | not itself a user-facing stage |

The capability manifest exposes this mapping.

The browser must not render `phase-3` as a permanent product concept.

**KSA-REQ-080** — Native phase identifiers must remain adapter/install metadata.

**KSA-REQ-081** — Stage mapping changes in a later Siesta revision must be handled by the adapter/capability manifest before general Kallula code changes are considered.

---

# 18. Work-Item Normalization

Current Siesta plans issues in `issues.md` and uses numbered headings such as `Issue #N`.

The baseline adapter maps each native issue to a Kallula Work Item.

Normalized identity must not rely only on the human-readable title.

For the current baseline, the adapter may use the tuple:

```text
(engine installation, Run, native issue number)
```

as its stable native correlation while the plan version remains unchanged.

If Siesta replans and issue numbering/content changes in a future version, the adapter must version/reconcile the plan rather than pretending an old issue identity is unchanged.

Work-item completion remains grounded in engine evidence such as KB decision nodes, tests, and commits—not merely the presence of a heading or a model statement.

---

# 19. Artifact Mapping

Kallula indexes native artifacts; it does not copy their semantic authority into editable database duplicates.

For the reviewed baseline, the adapter recognizes at least:

| Normalized artifact class | Current native location/pattern | Authority/use |
|---|---|---|
| `intent_transcript` | `interview_output.txt` | interview evidence/current finalized intent input |
| `intent_closeout_evidence` | `interview_closeout.txt` | diagnostic evidence when autonomous closeout occurs |
| `specification` | `spec.md` | engine-generated project specification |
| `implementation_plan` | `issues.md` | engine-generated issue plan |
| `project_knowledge` | `kb/graph.json` | authoritative Siesta Project KB |
| `knowledge_schema` | `kb/schema.json` | native KB schema |
| `engine_checkpoint` | `.pipeline-checkpoint` | native resume checkpoint; opaque to general Kallula code |
| `engine_idea_record` | `.pipeline-idea` | native collision/resume bookkeeping |
| `verification_verdict` | `verify_verdict.txt` | native persisted verification verdict |
| `issue_output` | `issue_*_output.txt` and related retry/consult/proxy artifacts | raw execution evidence |
| `test_evidence` | `regression_*.log` and related evidence | native mechanical evidence |
| `pre_issue_context` | `pre_issue_*.json` | diagnostic/provenance evidence |
| `issue_learning` | `learning_issue_*.txt` | native learning evidence |
| `project_learning` | `project_learning.*` | project-level learning evidence |
| `source_tree` | workspace excluding engine runtime/evidence according to export rules | generated application source |
| `git_repository` | `.git/` | canonical source history/recovery base |
| `recovery_archive` | `.git/siesta-recovery/` | blocked/dirty-work recovery evidence |

Patterns may evolve. They belong in the adapter's versioned artifact mapping, not scattered through Kallula.

## 19.1 Artifact indexing rule

Artifact indexing must tolerate an artifact being absent when the relevant capability/stage has not produced it.

Absence must not be converted into a false success/failure unless Siesta semantics explicitly require the artifact.

## 19.2 Raw diagnostics

Raw engine output artifacts remain available for diagnostics according to retention/security policy, but the UI should prefer normalized evidence where possible.

**KSA-REQ-090** — Artifact discovery must be adapter-owned and versioned with the Engine Installation.

**KSA-REQ-091** — Kallula must read source/download data from the canonical workspace, not regenerate source from artifact metadata.

**KSA-REQ-092** — Native bookkeeping artifacts must not be exposed as user-editable product settings.

---

# 20. Structured Engine Outcome

The adapter must receive a semantic outcome from Siesta.

At minimum, it must be possible to distinguish:

```text
WAITING_FOR_HUMAN
STOPPED_SAFE
COMPLETED_VERIFIED
TERMINAL_UNVERIFIED_OR_INCOMPLETE
FAILED
```

The exact enum/class name is not fixed, but these distinctions are mandatory.

Outcome data should include, when known:

- native checkpoint;
- verification verdict;
- blocked native issues;
- final/current Git commit identity;
- pending interaction identity;
- failure category/message;
- whether resume is potentially supported;
- important artifact references.

## 20.1 Exit-code compatibility

Standalone CLI exit codes may remain meaningful for shell users.

Kallula must not infer semantic outcome solely from them because current Siesta can use a clean exit for safe stop and a non-zero exit for a resumable incomplete result.

**KSA-REQ-100** — Safe stop and successful completion must be distinguishable without parsing human-readable log strings.

**KSA-REQ-101** — Verification failure/incomplete work must not be translated to `COMPLETED` merely because source was generated.

---

# 21. Safe-Stop Adaptation

The normalized Kallula operation is `request safe stop`.

The baseline adapter is allowed to implement this with current Siesta's native stop marker mechanism.

Conceptually:

```text
Kallula STOP_REQUESTED
        ↓
Adapter requests native stop
        ↓
current Siesta stop marker becomes present in canonical workspace
        ↓
Siesta reaches supported issue boundary
        ↓
engine records native halt evidence
        ↓
structured STOPPED_SAFE outcome/event
        ↓
Kallula transitions to STOPPED
```

## 21.1 Native mechanism isolation

General Kallula APIs, database state, frontend labels, and user documentation must not require knowledge of `stop.md`.

## 21.2 Boundary capability

For the reviewed baseline, safe stop is guaranteed at supported execution issue boundaries, not at an arbitrary instruction inside a Pi call.

The capability manifest must say this explicitly.

## 21.3 Stop/completion race

If stop is requested after the last supported safe boundary and the engine legitimately reaches a terminal completion result first, Kallula must record the stop request but use the real engine terminal result. It must not rewrite completion into a fictitious stop.

## 21.4 Stop cleanup

Before resuming a safely stopped Run, the adapter must ensure the native stop condition no longer causes immediate re-stop, while retaining historical stop evidence outside mutable marker state.

**KSA-REQ-110** — Adapter stop translation must be idempotent.

**KSA-REQ-111** — A repeated stop command must not create contradictory native stop state.

**KSA-REQ-112** — Kallula must only report `STOPPED` after structured/native evidence confirms a supported safe halt.

---

# 22. Resume Adaptation

Resume means continuing the same Kallula Run against its existing canonical workspace and Run Engine Runtime.

The adapter must never implement resume by creating a fresh project from the original prompt.

The baseline flow is:

```text
Kallula selects stopped/failed Run
        ↓
pinned Engine Installation resolved
        ↓
Run Engine Runtime restored
        ↓
canonical workspace mounted
        ↓
adapter inspects native state
        ↓
resume compatibility validated
        ↓
new Execution Attempt starts
        ↓
Siesta continues native checkpoint/issue ledger
```

The current `--resume` behavior may be used internally where appropriate, but Kallula's semantic resume does not depend on exposing that flag.

**KSA-REQ-120** — Resume must preserve Project Git history, Project KB, issue-completion ledger, checkpoint, verification evidence, and Run-scoped learned assets.

**KSA-REQ-121** — Resume must use the Run's pinned Engine Installation by default.

**KSA-REQ-122** — If the pinned installation is unavailable, Kallula must not silently substitute the current default installation.

**KSA-REQ-123** — Cross-version resume requires explicit validated compatibility.

---

# 23. Native State Descriptor

The adapter must inspect a workspace without running the full autonomous pipeline and return a **Native State Descriptor**.

Conceptually it includes:

- engine state-format identifier/version;
- native checkpoint value;
- whether a pending human interaction exists;
- plan/work-item presence;
- completed/blocked issue summary;
- verification verdict presence/value;
- Git repository presence;
- current HEAD identity if available;
- dirty-worktree indication;
- relevant recovery residue;
- whether the workspace appears terminal according to the pinned engine;
- native consistency warnings.

This descriptor is diagnostic/compatibility input. It does not replace native files as authority.

**KSA-REQ-130** — Workspace inspection must not mutate the project under ordinary successful inspection.

**KSA-REQ-131** — A malformed/unknown native state must be reported rather than silently normalized as a clean new project.

---

# 24. Compatibility Model

Kallula must not represent “compatible” as one undifferentiated boolean.

Three compatibility dimensions are required.

## 24.1 Launch compatibility

Can this Engine Installation execute correctly in the current Kallula worker environment and satisfy the adapter contract for a **new Run**?

## 24.2 State-format compatibility

Can this adapter/engine pair correctly read and interpret a workspace/checkpoint produced by a specified prior engine installation?

## 24.3 Resume compatibility

Given this **specific Run's actual native state**, is it safe to continue execution under a specified installation?

Resume compatibility may depend on more than state-format version, including:

- checkpoint stage;
- pending interaction format;
- issue plan/ledger expectations;
- verification semantics;
- skill/runtime snapshot;
- known migration constraints.

The default policy is conservative:

> A Run resumes on its pinned Engine Installation. Cross-installation resume is denied unless explicitly validated.

**KSA-REQ-140** — Semantic-version similarity or Git ancestry alone must not establish resume compatibility.

**KSA-REQ-141** — Every installation must declare a native state-format identifier/version.

**KSA-REQ-142** — Cross-version state compatibility must be backed by compatibility tests or an explicit migration contract.

---

# 25. Native State Format Version

The Kallula-compatible Siesta build should expose a small explicit state-format version independent of the marketing/project version.

It represents the compatibility contract for native persisted control artifacts relevant to resume, including at least:

- checkpoint meaning;
- pending-interaction state;
- issue completion ledger interpretation;
- verification verdict interpretation;
- required project bookkeeping used on resume.

A code change that does not affect persisted-state interpretation need not increment this format version.

A change that alters persisted-state meaning must.

This is not a replacement for exact engine revision pinning; it is an additional compatibility signal.

---

# 26. Agent Slot Mapping

Kallula exposes normalized Agent Slots from the Engine Installation capability manifest.

For the reviewed Siesta baseline:

| Kallula slot ID | Current native route | Current responsibilities |
|---|---|---|
| `planner` | `planner` | interview, specification, planning |
| `worker` | `worker` | implementation, review work, verification model calls |
| `consultant` | `consultant` | advice, approval proxy, learning |

Reviewer/proxy/learner are orchestration uses of these routes, not independent configurable slots in the current baseline.

The UI may present friendly labels, but the Run snapshot records normalized slot identity and resolved native mapping.

**KSA-REQ-150** — The adapter must expose Planner/Worker/Consultant as three configurable slots for the reviewed baseline.

**KSA-REQ-151** — Kallula must not fabricate separate configurable Reviewer/Learner slots unless a future engine installation actually supports them.

**KSA-REQ-152** — A future Siesta route topology change must update the capability manifest without requiring Project/Run domain redesign.

---

# 27. Agent Configuration Mapping

Current Siesta's committed model configuration supports, per route:

- `model`;
- `provider`.

Current phase code also chooses thinking behavior internally; arbitrary per-slot reasoning settings, prompt editing, and skill enable/disable are not generally exposed as safe config fields by the reviewed baseline.

Therefore the baseline capability manifest must be honest about what is supported.

## 27.1 Initial editable fields

For the first supported installation, Kallula may expose:

- provider;
- model;

subject to adapter validation.

Additional fields may be added only when the adapted engine has a tested mechanism for them.

## 27.2 Locked protocol behavior

Kallula must not allow user configuration to overwrite or remove engine protocol requirements that mechanical orchestration depends on.

Examples include marker contracts used by review, proxy, verification, and learning.

## 27.3 Materialization

Before a Run starts, the adapter materializes the immutable Run Agent Profile snapshot into the Run Engine Runtime in the exact native form needed by the pinned Siesta revision.

For the reviewed baseline this includes generating the Run-scoped `config/models.json`.

**KSA-REQ-160** — Historical Run attribution must retain the effective normalized configuration and the native materialized configuration hash/reference.

**KSA-REQ-161** — Unsupported configuration fields must be rejected before engine launch when the capability manifest can determine that they are unsupported.

---

# 28. Provider and Model Validation

The reviewed baseline is explicitly configured for Pi with an Ollama provider and default cloud model identifiers.

Kallula must distinguish:

- syntactically accepted configuration;
- adapter-declared provider support;
- worker-runtime provider availability;
- model reachability;
- native tool compatibility;
- served context-window compatibility.

A string being accepted by Pi's CLI is not enough to advertise it as a supported Kallula configuration.

The initial capability manifest should advertise only provider/model combinations or provider classes that the installation validation strategy can actually test.

Model-specific runtime checks may remain installation/environment validation rather than static PRD rules.

---

# 29. Skills and Learning Isolation

Current Siesta has:

- adapted repository skills under `.agents/skills/`;
- factory skills under `factory/skills/`;
- learner behavior capable of rewriting factory skills.

Kallula adaptation rules are:

1. adapted upstream/repository skills from the Engine Installation are immutable for a Run unless a deliberate capability later allows safe customization;
2. factory skills are materialized into the Run Engine Runtime;
3. the learner may mutate only that Run-scoped writable copy;
4. every skill used by a Run must have a content identity/hash/version in the Run reproducibility snapshot;
5. learner changes must be auditable as native evidence/events;
6. resumed Attempts of the same Run use the Run's evolved skill state;
7. new Runs do not silently inherit another Run's learner changes.

## 29.1 Promotion is deferred

A future product may let a user review and promote a learned skill into a new reusable Engine Learning Profile/Agent Profile version.

That workflow is outside the first adaptation.

**KSA-REQ-170** — Shared Engine Installation skill files must remain read-only during autonomous Runs.

**KSA-REQ-171** — Skill updates must not mutate the engine installation in place.

**KSA-REQ-172** — Run-level skill mutations must survive resumed Attempts of that Run.

---

# 30. Global KB Adaptation

Current Siesta's factory-level global KB is designed as local cross-project runtime memory.

The initial hosted Kallula design must not let unrelated Runs concurrently mutate one shared JSON graph because:

- current Graph concurrency is unsupported;
- cross-user/project contamination would be undesirable;
- reproducibility would become ambiguous;
- one Run could change context observed by another active Run.

Therefore:

- each Run Engine Runtime receives a global KB initialized from the pinned installation's seed/baseline learning profile;
- learning may append to the Run-scoped copy;
- the Project KB remains in the canonical Project workspace and persists across Runs naturally as project state;
- automatic global cross-project learning promotion is deferred.

This is a deliberate hosted adaptation of Siesta's local-machine behavior.

**KSA-REQ-180** — No active Runs may concurrently write one shared baseline `global-graph.json`.

**KSA-REQ-181** — The global KB baseline used by a Run must be attributable/versioned.

---

# 31. Child-Process Environment Isolation

> **Normative security reference:** [`Kallula — Security & Credentials Design.md`](./Kallula%20%E2%80%94%20Security%20%26%20Credentials%20Design.md), especially §§20–24, defines the credential domains, worker/Pi allowlist policy, provider credential exposure rules, and Project-secret denial/injection semantics that this adapter must implement.

The reviewed Siesta `_child_env()` inherits the entire parent environment.

Kallula requires defense in depth.

## 31.1 Worker-level boundary

The Execution Worker itself must be launched without Kallula control-plane secrets that the project/agent does not need.

Examples that must not normally enter the worker:

- Kallula database credentials;
- GitHub publishing credentials;
- host SSH keys;
- cloud-control credentials;
- unrelated project secrets;
- Docker daemon credentials/socket access.

## 31.2 Pi child boundary

The adapted Siesta invocation wrapper must accept/build an explicit child environment rather than blindly copying all environment variables from its parent.

The Pi child environment may include only values needed for:

- process execution (`PATH` and required runtime basics);
- the isolated Pi profile/config;
- Siesta's required Python path/runtime pointers;
- model-provider access explicitly authorized for the engine runtime;
- non-secret locale/runtime settings;
- future explicitly approved project execution values.

## 31.3 Provider credentials

If model-provider authentication is needed inside the worker, it must be scoped specifically to model invocation and must not imply access to unrelated Kallula infrastructure.

The Security & Credentials Design defines the secret-domain, injection, and redaction policy; the upcoming Execution Environment & Preview Design will choose the concrete runtime mechanism.

**KSA-REQ-190** — The adapted `_child_env` equivalent must be constructed from an explicit allowed base rather than `os.environ` wholesale.

**KSA-REQ-191** — Environment-isolation tests must assert the absence of representative forbidden Kallula secrets in the Pi process environment.

**KSA-REQ-192** — Necessary environment keys must be documented/tested so filtering cannot silently break native Siesta operations.

---

# 32. Pi Process and Diagnostic Handling

Current Siesta appropriately distinguishes model stdout from provider stderr for protocol parsing.

Kallula should preserve this.

The adapter should capture:

- engine stdout/stderr;
- native Pi/provider diagnostic artifacts already produced by Siesta;
- structured events separately;
- worker process exit metadata;
- timeout information.

Raw diagnostics must not become the semantic source of truth when structured outcomes/events exist.

Logs must be subject to later redaction/retention policy before user presentation.

**KSA-REQ-200** — Provider stderr must not be parsed as if it were a model protocol response.

**KSA-REQ-201** — Raw logs must retain enough correlation to identify Run and Attempt without embedding secret values.

---

# 33. Git Ownership and Integration

Siesta currently initializes and commits the generated Project repository and uses Git as part of recovery and issue completion.

Kallula must preserve that engine-owned local Git behavior.

The adapter may inspect Git to normalize evidence, but it must not create a parallel source history.

Kallula's external GitHub publishing service remains separate and trusted; autonomous Siesta/Pi processes do not need GitHub publishing credentials merely because the local workspace is a Git repository.

## 33.1 Commit event translation

When Siesta creates a successful local commit, the engine/adapter should emit/index:

- commit hash;
- commit subject where safe;
- related stage/work item when known.

## 33.2 Failed commit

A failed commit must remain visible as diagnostic/reliability evidence. The adapter must not invent a commit because an issue output claims success.

---

# 34. Verification Mapping

Kallula treats current Siesta's verification result as the engine's authoritative mechanical outcome for the generated Project, subject to any additional Kallula-level gates defined later.

The adapter maps:

- native persisted `VERIFY_PASSED` and its mechanical evidence → normalized engine verification passed;
- failure/unknown/incomplete verdict → not verified;
- blocked issue state → project incomplete regardless of optimistic model language.

A Kallula Verified State may be created only when architecture/PRD criteria are satisfied and the exact source identity is captured.

**KSA-REQ-210** — Adapter normalization must never turn `VERIFY_UNKNOWN`, failed verification, blocked issues, missing required test evidence, or failed review into a verified result.

**KSA-REQ-211** — Verification evidence must reference the exact Git/source state it validated when that identity is available.

---

# 35. Failure Classification

The adapter must help Kallula distinguish at least:

## 35.1 Engine-declared incomplete result

Siesta ran correctly but produced blocked work or failed verification and expects a later resume.

## 35.2 Engine failure

Siesta raised/returned an unexpected failure within engine logic.

## 35.3 Adapter failure

The Kallula-owned translation/integration layer failed independently of Siesta semantics.

## 35.4 Worker/runtime failure

The hosting process/container/VM disappeared, timed out externally, lost storage, or was killed.

## 35.5 Configuration incompatibility

The selected Run configuration cannot be represented/supported by the pinned Engine Installation.

## 35.6 State incompatibility

The requested engine cannot safely interpret/resume the stored native state.

These categories map into Kallula failure/recovery behavior defined by the architecture.

**KSA-REQ-220** — A worker disappearance must not be reported as an engine-declared failure until reconciliation establishes what happened.

**KSA-REQ-221** — Adapter exceptions must carry enough classification for the Reconciler/UI to avoid blaming Siesta for Kallula integration faults.

---

# 36. Correlation and Idempotency

Every Execution Attempt must provide correlation context to the adapter.

At minimum:

- Project ID;
- Run ID;
- Attempt ID;
- Engine Installation ID;
- immutable Run configuration identity.

Native event/interaction IDs are mapped to Kallula identities without replacing them.

## 36.1 Interaction idempotency

The Kallula Pending Interaction owns answer acceptance exactly once.

The engine owns answer consumption into native interview state.

The adapter bridges them using the stable native interaction ID.

If delivery is retried after an uncertain network/process outcome, the engine must determine whether the native interaction already consumed that answer.

## 36.2 Event idempotency

The event hook may emit the same native transition again during retries/recovery.

For the initial adapted Siesta build, the adapter/event-sink wrapper assigns a monotonically increasing **adapter event sequence within the Execution Attempt** when each structured native event is first accepted by the adapter. The stable ingestion key is conceptually:

```text
(Attempt ID, adapter event sequence)
```

If delivery to the Control Plane is retried within that Attempt, the same sequence/key must be reused. A restarted worker is a new Attempt and therefore gets a new sequence namespace.

Native correlation fields such as phase, issue number, interaction ID, or commit hash remain attached for diagnostics and semantic reconciliation. Critical product state is still reconciled from native workspace evidence after process loss; the event stream is not allowed to fabricate completion merely because an event was missed before a crash.

Kallula persistence should deduplicate repeated deliveries by this stable source key and treat intentionally repeated diagnostic events as separate only when the adapter assigns a new occurrence sequence.

---

# 37. Capability Manifest

Every supported Engine Installation must publish a capability manifest generated/validated by the adapter.

The serialization format is delegated to the API/Data Contract Specification, but the manifest must represent the following semantics.

## 37.1 Identity

- engine family;
- upstream repository identity;
- exact upstream revision;
- Kallula patch-set/adapted-build identity;
- adapter version;
- native state-format version;
- capability-manifest schema version.

## 37.2 Execution capabilities

- new project execution;
- auto requirements mode;
- interactive requirements mode;
- cooperative human suspension;
- resume;
- safe stop;
- supported safe-stop boundaries;
- work-item model;
- review;
- verification;
- learning.

## 37.3 Stage model

Ordered/related native stages and their normalized Kallula mapping.

## 37.4 Agent slots

Each slot's:

- normalized ID;
- native route;
- purpose;
- editable config fields;
- locked fields;
- validation constraints.

## 37.5 Artifact model

Normalized artifact classes mapped to native discovery rules.

## 37.6 Environment requirements

- required executables/runtimes;
- Pi expectations;
- provider expectations;
- required environment key categories;
- optional context probes.

## 37.7 Compatibility metadata

- state-format version;
- known resume-compatible predecessor installations, if any;
- compatibility-suite result/status;
- restrictions/warnings.

**KSA-REQ-230** — Capabilities must be explicit data, not inferred by the frontend from an engine version string.

**KSA-REQ-231** — An unsupported/unknown capability must default to disabled, not optimistically enabled.

---

# 38. Baseline Capability Declaration

For the reviewed and Kallula-adapted Siesta baseline, the expected capability declaration is about:

| Capability | Baseline adapted status |
|---|---|
| New project execution | supported |
| Interactive requirements | supported after Human Interaction adaptation |
| Auto requirements | supported |
| Browser-independent waiting | supported after cooperative suspension adaptation |
| Resume same Run | supported on pinned installation |
| Cross-version resume | not supported by default |
| Safe stop | supported at declared issue boundaries |
| Structured stages | supported via event hook/mapping |
| Structured work items | supported from issue plan/engine events |
| Test evidence | supported |
| Review evidence | supported |
| Verification evidence | supported |
| Git commit evidence | supported |
| Agent slots | Planner / Worker / Consultant |
| Agent provider/model config | supported |
| Arbitrary per-slot prompt editing | not supported |
| Arbitrary skill toggling | not supported initially |
| Self-learning factory skills | supported only in Run-scoped mutable copy |
| Shared automatic cross-Run learning | disabled/deferred |
| Existing repository import | Kallula feature requires separate repository flow validation; not implied by current CLI baseline |
| Arbitrary project-secret exposure | not supported |
| Web preview orchestration | Kallula execution-environment capability, not a Siesta engine capability |

This table is not a promise for future revisions. The registered capability manifest for each Engine Installation is authoritative.

---

# 39. Adapter Responsibilities

The Kallula Siesta Adapter is responsible for:

- validating the selected installation and Run configuration;
- materializing the Run Engine Runtime;
- supplying the canonical workspace;
- translating Kallula execution intent into the Siesta programmatic entrypoint;
- supplying interaction/event/environment hooks;
- converting native pending interactions into adapter outputs;
- supplying accepted answers on resumed Attempts;
- translating safe-stop requests into native behavior;
- inspecting native state for resume/reconciliation;
- normalizing stages, work items, outcomes, and artifacts;
- capturing raw diagnostics;
- classifying adapter vs engine failures;
- reporting capabilities;
- enforcing installation identity;
- performing adapter-side compatibility checks.

The adapter must **not** own:

- Kallula Run-state persistence;
- user authentication;
- global event ordering sequence;
- Project execution leases;
- GitHub publishing credentials;
- browser sessions;
- notification delivery;
- preview ingress;
- general credential storage.

---

# 40. Control Plane and Coordinator Responsibilities at the Boundary

The Control Plane/Coordinator is responsible for:

- selecting the pinned Engine Installation;
- creating immutable Run configuration snapshots;
- owning Project/Run/Attempt lifecycle;
- acquiring/releasing Project execution leases;
- persisting normalized commands/events/interactions;
- accepting human answers exactly once;
- deciding whether a stopped/failed Run may be queued for another Attempt after compatibility inspection;
- keeping Kallula state truthful when worker state is uncertain;
- calling reconciliation after crashes;
- presenting only capabilities declared by the adapter/install.

It must not:

- write `.pipeline-checkpoint` directly;
- manually mark Siesta issues completed;
- fabricate `VERIFY_PASSED`;
- edit the Project KB to force product state;
- parse `stop.md` as a frontend feature;
- rewrite native artifacts to make a failed Run look successful.

---

# 41. Runner/Worker Responsibilities

The Worker boundary is responsible for:

- providing filesystem access to the canonical workspace;
- providing access to the immutable Engine Installation and Run Engine Runtime;
- launching only the pinned adapter/engine identity;
- enforcing resource/network/sandbox policy defined later;
- exposing only approved environment/credentials;
- reporting process liveness and exit information;
- allowing the adapter to write native engine/project state where authorized.

The Worker is disposable.

It must not be the only location containing:

- Project source;
- pending interactions;
- Kallula Run state;
- accepted human answers;
- immutable Run configuration.

---

# 42. Upstream Siesta Update Strategy

Kallula should track upstream Siesta rather than diverging indefinitely.

## 42.1 Source strategy

The recommended maintenance model is:

- retain upstream `jairorodriguezarias/siesta` as the source project;
- pin an exact upstream revision per Engine Installation;
- maintain a minimal Kallula integration patch set/fork only for seams not yet upstream;
- keep the Kallula adapter itself in Kallula-owned code, not embedded throughout Siesta;
- upstream generic improvements when practical;
- preserve Siesta and third-party license notices.

## 42.2 Patch categories

Kallula-specific patches should be grouped by purpose rather than mixed with unrelated engine changes:

```text
01-programmatic-entrypoint
02-external-workspace
03-human-interaction-channel
04-event-sink
05-structured-outcome
06-child-environment
07-state-format-capabilities
```

This is conceptual organization; it does not mandate a particular Git patch tool.

## 42.3 Upgrade workflow

```text
Select new upstream commit
        ↓
reapply/rebase generic Kallula engine seams
        ↓
resolve compile/test changes
        ↓
build candidate Engine Installation
        ↓
run upstream Siesta tests
        ↓
run Kallula adapter unit tests
        ↓
run Kallula engine compatibility suite
        ↓
compare capability manifest
        ↓
classify launch/state/resume compatibility
        ↓
register SUPPORTED or REJECTED candidate
        ↓
optionally make default for NEW Runs
```

## 42.4 No silent auto-upgrade

A deployment updating Kallula application code must not silently replace the engine revision used by existing Runs.

**KSA-REQ-240** — Every production Run must be attributable to an exact upstream Siesta revision and exact adapter/adaptation identity.

**KSA-REQ-241** — Upstream changes that break the integration surface must fail compatibility registration before becoming a default engine.

---

# 43. Engine Compatibility Suite

A candidate Siesta Engine Installation cannot be marked supported based only on unit tests or successful import.

The compatibility suite must exercise real integration semantics with deterministic/fake model boundaries where appropriate and at least periodic real-model validation where model/tool compatibility matters.

## 43.1 Installation/introspection

Validate:

- exact identity is reportable;
- capability manifest is valid;
- required engine/runtime files exist;
- adapter can load the integration surface;
- standalone CLI still works for a basic fixture.

## 43.2 External workspace

Validate:

- a Kallula-supplied workspace is used exactly;
- slug collision behavior cannot redirect Kallula to another directory;
- no second project copy is created;
- Git/KB/checkpoint artifacts appear in the supplied workspace.

## 43.3 Interactive suspension/resume

Validate:

1. engine produces a requirements question;
2. pending native interaction is persisted;
3. engine returns `WAITING_FOR_HUMAN` without failure learning;
4. worker/process can terminate;
5. a new Attempt receives the answer;
6. exact pending interaction consumes it once;
7. transcript preserves prior turns;
8. next question/finalization continues correctly;
9. duplicate delivery does not duplicate the answer;
10. final intent confirmation can also survive process restart.

## 43.4 Auto mode

Validate that auto mode completes Phase 0 without creating a spurious Pending Interaction.

## 43.5 Stage/event mapping

Validate that significant phase/work-item transitions produce structured native events and normalize into the expected stage/work-item concepts.

## 43.6 Mechanical gates

Validate that:

- failing tests cannot become success;
- absent required tests cannot be presented as passed verification;
- failed review/proxy approval cannot become review success;
- blocked work cannot become completed;
- verification evidence is preserved.

## 43.7 Safe stop

Validate:

- repeated stop requests are harmless;
- stop during execution is observed at supported boundary;
- result is `STOPPED_SAFE`, not `COMPLETED`;
- Kallula/native evidence identifies the boundary;
- resume clears transient stop condition and continues existing state.

## 43.8 Resume

Validate resume from fixtures representing:

- planning complete / execution pending;
- partially completed issues;
- blocked issue;
- post-execution/pre-review;
- failed review after repair opportunity;
- failed verification;
- safely stopped execution;
- pending Phase 0 interaction;
- completed project (must not duplicate completion/learning).

## 43.9 Crash/reconciliation inspection

Kill the worker at representative points and verify that workspace inspection can describe state without inventing completion.

## 43.10 Environment isolation

Inject sentinel “forbidden secrets” into the Kallula parent/control environment and verify they are absent from the Pi child environment.

Also verify required runtime variables remain present so the engine still functions.

## 43.11 Agent configuration

For each exposed Agent Slot:

- materialize provider/model config;
- verify Siesta reports/uses the intended assignment;
- reject unsupported fields/combinations;
- preserve configuration snapshot/hash.

## 43.12 Learning isolation

Run two separate fixtures and verify:

- Run A can mutate its Run-scoped factory skill copy;
- Run B's copy is unchanged;
- resumed Attempt A sees A's modified copy;
- immutable Engine Installation files remain unchanged.

## 43.13 Artifact discovery

Produce a representative successful and failed run and validate normalized artifact discovery against actual files/evidence.

## 43.14 Git/recovery

Validate issue commits and blocked-work recovery archives remain consistent with upstream Siesta's own recovery tests.

---

# 44. Compatibility Status Model

An Engine Installation registration should have a support status concept equivalent to:

- `CANDIDATE` — built but not validated;
- `SUPPORTED_NEW_RUNS` — launch-compatible for new Runs;
- `SUPPORTED` — fully supported for its own pinned Runs;
- `REJECTED` — failed required compatibility tests;
- `DEPRECATED` — no longer default for new Runs but retained for pinned historical/resumable Runs where operationally possible.

Cross-installation resume compatibility is recorded separately as an explicit relationship, not implied by both installations being `SUPPORTED`.

The final persistence representation belongs in the API/Data Contract Specification.

---

# 45. Migration and Cross-Version Resume

The first Kallula release does not need automatic Siesta state migration.

The safe baseline is:

```text
Run created on Engine Installation A
        ↓
all Attempts for that Run use A
```

If future operational needs require migration from A to B:

1. B's adapter must declare support for A's native state format;
2. compatibility fixtures from A must pass under B;
3. any transformation must be explicit and testable;
4. original state must be retained/backed up before migration;
5. migration must produce an auditable event;
6. failure must leave the original resumable state intact.

No migration is preferable to a guessed migration.

---

# 46. Raw Evidence and Provenance

The adapter should retain a clear chain:

```text
Kallula Run / Attempt
    ↓
Engine Installation + adapter identity
    ↓
Native stage/work item
    ↓
model/provider invocation evidence
    ↓
source/test changes
    ↓
Git commit/recovery action
    ↓
review/verification evidence
    ↓
normalized event/artifact index
```

Kallula does not need to display every raw detail by default, but enough evidence must remain available to diagnose discrepancies.

Native evidence must be attributed, not rewritten into a cleaner fictional history.

---

# 47. Security Boundary Notes for This Adapter

Detailed threat modeling and credential-flow policy are now resolved by [`Kallula — Security & Credentials Design.md`](./Kallula%20%E2%80%94%20Security%20%26%20Credentials%20Design.md). The adapter must implement, and may not weaken, these non-negotiable boundaries:

- no Kallula database credentials in autonomous worker/Pi environments;
- no GitHub publishing token merely for local Git operations;
- no host SSH key inheritance;
- no Docker socket/daemon capability by default;
- no unrelated Project secrets;
- no routine plaintext secret persistence in engine artifacts;
- raw logs/artifacts are potentially sensitive and must be handled accordingly;
- Project workspaces from different owners/projects must not be accidentally cross-mounted;
- immutable Engine Installation content should not be writable by autonomous agents.

---

# 48. Implementation Sequence for the Adapter

Implementation should proceed in narrow, testable slices.

## Slice 1 — Programmatic engine + external workspace

Prove:

```text
adapter invokes pinned Siesta
    ↓
Kallula-supplied workspace used
    ↓
auto-mode tiny project completes
    ↓
structured outcome returned
```

Do not build full UI around it yet.

## Slice 2 — Structured events

Add source-level phase/work-item/verification events and prove Kallula can observe a complete auto Run without parsing console text.

## Slice 3 — Durable human interaction

Add cooperative Phase 0 suspension, persisted native interaction state, answer resume, and final-confirmation resume.

This is the most important behavioral slice.

## Slice 4 — Safe stop/resume

Translate safe stop, capture structured stopped outcome, then resume with a new Attempt against identical Run/workspace state.

## Slice 5 — Run-scoped runtime assets

Materialize per-Run model config, mutable factory skills, and Run-scoped global KB. Prove learning isolation.

## Slice 6 — Environment isolation

Replace child environment inheritance and validate sentinel-secret exclusion.

## Slice 7 — Capability manifest + installation validation

Generate/validate the full manifest and compatibility suite before marking the baseline installation supported.

This sequencing proves one seam at a time without requiring final distributed infrastructure.

---

# 49. Adaptation Acceptance Criteria

The Siesta adaptation specification is successfully implemented when the following are demonstrably true.

## AC-KSA-001 — Standalone parity

The adapted Siesta build can still execute a normal CLI project outside Kallula.

## AC-KSA-002 — External workspace

Kallula can run Siesta against an explicitly supplied durable workspace and no alternate slug-derived project copy is created.

## AC-KSA-003 — Browser-independent interview

Siesta can ask a requirements question, suspend the Execution Attempt, and later continue from a new Attempt after the browser/user returns.

## AC-KSA-004 — Exact pending question survives

A process restart while waiting does not cause Siesta to replace the pending human question with a different model-generated question before consuming the accepted answer.

## AC-KSA-005 — Exactly-once answer consumption

Retrying answer delivery cannot append the same answer twice or advance two interview turns.

## AC-KSA-006 — Final confirmation durability

Final intent confirmation survives worker termination just like a normal interview question.

## AC-KSA-007 — Structured stages

Kallula can determine requirements/specification/planning/execution/review/verification progress from structured engine/adapter events without parsing terminal decoration.

## AC-KSA-008 — Safe-stop truthfulness

A stop request is not normalized as stopped until Siesta reaches a declared safe boundary; a safe stop is distinguishable from successful completion.

## AC-KSA-009 — Resume truthfulness

A stopped/incomplete Run resumes the same workspace/native ledger rather than starting from the original idea.

## AC-KSA-010 — Mechanical verification preserved

Kallula cannot normalize a model's success statement over failing/missing required mechanical evidence.

## AC-KSA-011 — Agent-slot configuration

Planner, Worker, and Consultant model/provider choices from the immutable Run snapshot are materialized and observable in the execution evidence.

## AC-KSA-012 — Skill isolation

A learner modification in Run A cannot mutate Run B or the immutable Engine Installation.

## AC-KSA-013 — Global KB isolation

Concurrent Runs do not write one shared current-Siesta global JSON graph.

## AC-KSA-014 — Child secret isolation

Representative forbidden Kallula secrets present in a parent/control environment do not appear in Pi's environment.

## AC-KSA-015 — Artifact containment

General Kallula code can obtain specification, plan, verification, KB, Git, and diagnostic artifact references through the adapter without hard-coding current Siesta filenames.

## AC-KSA-016 — Engine pinning

A new default Siesta installation does not alter which engine revision an existing Run uses.

## AC-KSA-017 — Upgrade gating

A new upstream Siesta revision cannot become a supported/default Engine Installation until the compatibility suite succeeds.

## AC-KSA-018 — Cross-version fail closed

A Run is not resumed on a different Siesta installation merely because the new revision is newer or shares a state-format major version.

## AC-KSA-019 — Error attribution

Adapter failure, engine-declared incomplete result, engine failure, and worker loss are distinguishable in diagnostic/control state.

## AC-KSA-020 — Installation immutability

Completing Runs and learner activity leave the registered Engine Installation bytes unchanged.

---

# 50. PRD Traceability

This specification operationalizes the following PRD requirements/areas most directly:

| PRD requirement/area | Adaptation resolution |
|---|---|
| §8 Engine Evolution Contract | §§24–25, 37–45 |
| KAL-FR-023 | §§37–38 capability-aware engine/config selection |
| KAL-FR-040–046 | §§12–14 durable external human interaction |
| KAL-FR-050–053 | §§6–10, 20 execution identity/config boundary |
| KAL-FR-070–073 | §§15–16 structured events/native evidence |
| KAL-FR-080–083 | §21 safe-stop translation |
| KAL-FR-090–093 | §§22–25 resume/compatibility |
| KAL-FR-100–102 | §35 failure classification and fail-closed behavior |
| KAL-FR-110–123 | §§16–18, 34 work/test/review/verification evidence |
| KAL-FR-130–143 | §§11, 19 artifact/source authority |
| KAL-FR-150–164 | §33 local Git ownership vs external publishing |
| KAL-FR-200–205 | §§26–28 Agent Slot/config capability mapping |
| KAL-FR-210–212 | §§10, 27 immutable Run profile materialization |
| KAL-FR-220–224 | §§10, 29–30 skill/learning isolation |
| KAL-FR-240–243 | §31 child environment and secret boundary |
| KAL-FR-250–252 | §§19, 30 Project KB/global KB handling |
| KAL-FR-270–281 | §§19–24 evidence/history/engine identity |
| KAL-NFR-REL-004–008 | §§20–25, 34–35 truthful outcomes/recovery |
| KAL-NFR-MNT-001–009 | §§6–8, 37, 42–45 upstream containment/compatibility |
| §17 Engine Adapter Requirements | entire document |

---

# 51. Architecture Traceability

This specification refines—but does not redefine—the following architecture areas:

| Architecture area | This document defines |
|---|---|
| §7.6 Engine Adapter | exact Siesta-facing responsibility and process boundary |
| §§11–14 Run/Attempt lifecycle | how one Attempt invokes/suspends current Siesta |
| §15 Stage Model | current native-to-normalized stage mapping |
| §§17–19 Interaction/stop/resume | Siesta mechanisms that implement those semantics |
| §§22–25 events/artifacts/state | native event and artifact discovery rules |
| §§27–33 backend/recovery flows | engine-facing execution outcomes and inspection |
| §§35–37 installation/upgrades/capabilities | manifest, compatibility dimensions, suite, upstream workflow |
| §38 Agent Configuration | current Planner/Worker/Consultant slot mapping |
| §39 Self-Learning | Run-scoped skills/global KB adaptation |
| §42 trust boundary | explicit child environment requirements |
| §49 invariants | adapter-level acceptance criteria |

---

# 52. Remaining Deliberately Open Decisions

This document resolves the Siesta adaptation model. The following implementation choices remain intentionally open because another specification owns them or empirical implementation work should decide them.

## 52.1 Worker transport

How the Run Coordinator sends commands to and receives events from the Execution Worker: local process IPC, database-backed command queue, HTTP/RPC, or another mechanism.

The API/Data Contract Specification will define the durable contract after UX/security/execution designs are understood.

## 52.2 Physical Run Engine Runtime storage

The logical Run-scoped runtime must persist across Attempts, but its physical storage may be a durable filesystem path, volume, object materialization, or another simple mechanism appropriate to the chosen deployment.

## 52.3 Exact Python names/signatures

The semantic integration surface is fixed here. Exact class/function names should be chosen during implementation for clarity and upstream fit.

## 52.4 Exact event payload serialization

Required event semantics are fixed; transport/storage schema belongs in API/Data Contracts.

## 52.5 Shared learned-profile promotion

The initial system isolates Run learning. A future reviewed promotion workflow remains deferred.

## 52.6 Cross-version migration implementation

Not required for the first release. Pinned-engine resume is sufficient.

---


# 53. Implementation Status

The implementation plan now exists:

> [`Kallula — Implementation Plan.md`](./Kallula%20%E2%80%94%20Implementation%20Plan.md)

Use that document to sequence development and select the first-release implementation choices.

No more architecture document is required before coding starts.

The **Test & Compatibility Strategy** is still required before release. It is intentionally deferred until the implementation has real testable seams, runtime behavior, and compatibility fixtures.


# Appendix A — Reviewed Siesta Source Map

The adaptation analysis for the baseline primarily relies on these current repository areas:

| Source | Relevance |
|---|---|
| `README.md` | product behavior, usage, resume, artifacts, reliability summary |
| `AGENTS.md` | phase/role contracts, recovery, model configuration, KB/skills behavior |
| `factory/pipeline/__main__.py` | CLI entrypoint, workspace derivation, checkpoint dispatch, resume, terminal outcomes |
| `factory/pipeline/phases.py` | Phase 0 terminal interaction, issue execution, stop detection, review, verification |
| `factory/pipeline/pi.py` | Pi invocation, role config, timeout, current inherited child environment |
| `factory/pipeline/kb.py` | JSON Graph persistence semantics |
| `factory/pipeline/learn.py` | per-issue/project learning and mutable factory-skill updates |
| `factory/config/models.json` | Planner/Worker/Consultant provider/model routes |
| `factory/tests/test_integration.py` | end-to-end engine behavior fixtures |
| `factory/tests/test_mechanical_gates.py` | mechanical verification constraints |
| `factory/tests/test_recovery_gates.py` | real-Git recovery/resume behavior |
| `factory/tests/test_pi.py` | Pi invocation behavior |
| `factory/tests/test_phases.py` | phase/interview behavior |
| `factory/tests/test_kb.py` | KB persistence behavior |

This source map is descriptive for the pinned baseline and must be refreshed when registering a new upstream revision.

---

# Appendix B — Current Native-to-Kallula Mapping Summary

```text
Siesta idea/slug selection
    → hidden by external Kallula workspace injection

phase-0
    → requirements

phase-1
    → specification

phase-2
    → planning

phase-3
    → execution

phase-4
    → review

phase-5
    → verification

Phase 6
    → completion bookkeeping

Phase 7
    → learning

Planner
    → agent slot: planner

Worker
    → agent slot: worker

Consultant
    → agent slot: consultant

stop.md
    → native implementation of normalized safe-stop request

.pipeline-checkpoint
    → opaque native checkpoint artifact

issues.md issue number
    → native work-item correlation

verify_verdict.txt
    → native verification verdict artifact

kb/graph.json
    → project knowledge artifact

factory/skills mutable files
    → Run-scoped mutable engine assets in Kallula

factory/kb/global-graph.json
    → Run-scoped global learning context in initial Kallula design
```

---

# Appendix C — Adaptation Invariants

1. **The adapter is the only Kallula layer allowed to know current Siesta filenames and phase IDs.**
2. **The canonical Project workspace is supplied by Kallula; Siesta does not choose another one.**
3. **Human waiting is durable and may release the worker.**
4. **A pending human question is persisted before the Attempt ends.**
5. **An accepted answer is correlated and consumed once.**
6. **Native engine state remains authoritative for native resume semantics.**
7. **A clean process exit is not automatically completion.**
8. **Mechanical verification cannot be overridden by narrative/model claims.**
9. **Engine Installation content is immutable.**
10. **Mutable factory skills/global learning are Run-scoped initially.**
11. **Pi child environments are explicitly constructed, not inherited wholesale.**
12. **Every Run is pinned to an exact engine + adapter/adaptation identity.**
13. **A newer engine is not automatically resume-compatible.**
14. **Unsupported capabilities fail closed.**
15. **Upstream Siesta remains usable independently of Kallula.**

---

# Appendix D — Terminology

**Adapted Siesta build** — An exact upstream Siesta revision plus the minimal generic integration changes required by Kallula when those changes are not yet available upstream. **Kallula Siesta Adapter** — Kallula-owned translation code that is allowed to understand native Siesta semantics and exposes stable Kallula engine behavior. **Run Engine Runtime** — Mutable Run-scoped Siesta factory/config/learning assets derived from an immutable Engine Installation. **Native State Descriptor** — Non-mutating adapter interpretation of a Siesta workspace's resumable/control state. **Native interaction ID** — Stable engine-side identity for a pending human input point. **State-format version** — Explicit identity for persisted Siesta execution-state semantics relevant to interpretation/resume. **Launch compatibility** — Ability to use an Engine Installation for new execution. **State-format compatibility** — Ability to correctly understand prior persisted engine state. **Resume compatibility** — Ability to safely continue a specific existing Run under a specified installation. **Capability manifest** — Versioned declaration of supported engine behavior, stages, Agent Slots, artifacts, and compatibility metadata. **Engine Installation** — Immutable tested combination of exact Siesta revision/adaptation plus compatible adapter/capabilities.

---

# Final Adaptation Rule

> **Kallula may know that Siesta exists; the rest of Kallula must not need to know how today's Siesta works. The adapter owns that knowledge. Human interaction, events, outcomes, workspace identity, configuration, and compatibility must cross the boundary through explicit contracts, while Siesta remains free to evolve behind them.**


The **Test & Compatibility Strategy** remains required before release, but is intentionally deferred until implementation choices and testable seams are concrete.
