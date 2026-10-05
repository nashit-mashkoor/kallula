# Kallula — Execution Environment & Preview Design

**Document status:** Normative execution-runtime and Preview design — pre-implementation
**Product:** Kallula
**Primary product specification:** [`Kallula — Product Requirements Document.md`](./Kallula%20%E2%80%94%20Product%20Requirements%20Document.md)
**Parent architecture:** [`Kallula — System Architecture & State Model.md`](./Kallula%20%E2%80%94%20System%20Architecture%20%26%20State%20Model.md)
**Engine adaptation specification:** [`Kallula — Siesta Engine Adaptation Specification.md`](./Kallula%20%E2%80%94%20Siesta%20Engine%20Adaptation%20Specification.md)
**UX & interaction specification:** [`Kallula — UX & Interaction Specification.md`](./Kallula%20%E2%80%94%20UX%20%26%20Interaction%20Specification.md)
**Security & credentials design:** [`Kallula — Security & Credentials Design.md`](./Kallula%20%E2%80%94%20Security%20%26%20Credentials%20Design.md)
**API & data contract specification:** [`Kallula — API & Data Contract Specification.md`](./Kallula%20%E2%80%94%20API%20%26%20Data%20Contract%20Specification.md)
**Implementation plan:** [`Kallula — Implementation Plan.md`](./Kallula%20%E2%80%94%20Implementation%20Plan.md)  
**Implementation status:** Not started
**Purpose:** Define the physical execution model for Kallula: worker isolation, durable workspaces, Run Engine Runtime persistence, environment resolution, process/resource/network controls, dependency execution, application-service lifecycle, runtime secret injection, stable Preview source snapshots, Preview routing/access control, health/logging, cleanup, and crash reconciliation.
**Audience:** Backend/control-plane, runtime/infrastructure, security, engine-integration, Preview, frontend, QA, and operations engineers.

> **Normative relationship:** The PRD defines required behavior. The **System Architecture & State Model** defines lifecycle, ownership, leases, Runs, Execution Attempts, workspaces, events, reconciliation, and Preview as a product concept. The **Siesta Engine Adaptation Specification** defines how Siesta is invoked and resumed. The **Security & Credentials Design** defines what execution and Preview runtimes may access. The **UX & Interaction Specification** defines how runtime state is presented. This document is authoritative for the physical/runtime design that implements those constraints. The **API & Data Contract Specification** now represents Workspace, Run Engine Runtime, Environment Snapshot, Runtime Plan, Preview, Preview Service, source-snapshot, log, command, and failure identities without redefining this runtime model.

> **Core runtime rule:** The autonomous coding worker and the generated application runtime are separate security and lifecycle domains. A coding worker must not need Project runtime secrets merely because the generated application needs them.

> **Durability rule:** Containers/processes are disposable. The canonical Project workspace, Kallula control state, and Run Engine Runtime are durable according to their defined lifetimes.

---

# 1. Purpose

Kallula must safely execute an evolving software factory against persistent Project source, then let users run and inspect the generated application without turning autonomous code execution into control-plane authority.

This specification resolves the remaining physical questions:

- What is an Execution Worker?
- What runs inside it?
- What persists after it exits?
- Where is the canonical Project workspace stored?
- What exactly is the Run Engine Runtime?
- How does a new Execution Attempt attach to the same Run state?
- How are Environment Profiles resolved?
- What container/runtime assumptions are permitted?
- How are dependency installation and arbitrary build scripts contained?
- How are CPU, memory, process, disk, and time limits applied?
- What network access does a worker receive?
- How do generated applications run separately from coding agents?
- How do application services discover each other?
- How are Project runtime credentials injected without exposing them to Siesta/Pi?
- What source state does Preview actually run?
- How is Preview routed through the browser safely?
- How are Preview access, health, logs, restart, and cleanup represented?
- What happens when the runtime manager, worker, host, or Preview crashes?
- How does the design begin on one host without preventing later multi-host execution?

---

# 2. Design Goals

The execution design must satisfy the following goals.

## 2.1 Strong boundary with simple initial operations

The initial deployment may use one host and one database, but autonomous code still runs inside a real isolation boundary.

## 2.2 Persistent source, disposable compute

Destroying a worker must not destroy:

- Project source;
- Git history;
- Siesta per-project checkpoint/evidence;
- Run-scoped engine mutable state required for resume;
- normalized Kallula state.

## 2.3 Separate build authority from application authority

The coding worker may install dependencies and execute development/test commands.

The generated application runtime may receive Project runtime credentials.

Those permissions are not interchangeable.

## 2.4 Deterministic attribution

Every worker and Preview instance must be attributable to:

- Project;
- Run where applicable;
- Execution Attempt where applicable;
- source identity;
- Environment Snapshot;
- Engine Installation where applicable.

## 2.5 Safe evolution

Changing:

- Siesta;
- runtime images;
- Preview routing;
- storage implementation;
- execution host topology;

must not require redefining the Project/Run model.

## 2.6 No premature distributed infrastructure

The design must work correctly on one execution host before requiring:

- Kubernetes;
- a distributed queue;
- a service mesh;
- multi-region storage;
- autoscaling clusters.

---

# 3. Explicit Non-Goals

The initial design does not provide:

- production deployment of generated applications;
- arbitrary user-managed Docker Compose;
- privileged containers;
- nested Docker;
- host Docker socket access from workers;
- arbitrary host mounts;
- GPU scheduling unless separately designed;
- multi-region failover;
- multiple concurrent write workers on one Project;
- browser IDE execution terminals;
- persistent Preview databases as a guaranteed product feature;
- automatic horizontal Preview scaling;
- arbitrary inbound TCP exposure;
- production-grade secrets inside coding-agent tests;
- unrestricted custom container capabilities.

Preview is for development/demo/inspection, not production hosting.

---

# 4. Runtime Domains

```text
                 +----------------------+
                 |   Control Plane      |
                 +----------+-----------+
                            |
                            v
                 +----------------------+
                 | Runtime Manager      |
                 +----+-------------+---+
                      |             |
             Attempt  |             | Preview
                      v             v
           +----------------+   +----------------+
           | Coding Worker  |   | Preview Build  |
           | Siesta + Pi    |   +-------+--------+
           +---+--------+---+           |
               |        |               v
               |        |       +----------------+
               |        |       | App Runtime    |
               |        |       +-------+--------+
               |        |               |
               v        v               v
        +----------+ +----------+ +--------------+
        | Workspace| | Run      | | Preview      |
        | durable  | | Runtime  | | Gateway      |
        +----------+ +----------+ +--------------+
```


Kallula distinguishes four runtime domains.

```text
Control Plane
    │
    ▼
Execution Runtime Manager
    │
    ├── Execution Worker
    │      ├── Kallula Siesta Adapter
    │      ├── Siesta
    │      ├── Pi / coding agent
    │      └── development/test commands
    │
    └── Preview Runtime Group
           ├── application service(s)
           ├── supporting service(s)
           └── Preview network
                    │
                    ▼
               Preview Gateway
                    │
                    ▼
                  Browser
```

They have different trust and persistence characteristics.

## 4.1 Control Plane

Trusted product authority.

Owns:

- Project/Run state;
- leases;
- commands;
- credentials policy;
- Preview records;
- Engine Installation records;
- Environment Profiles/Snapshots;
- user authorization.

## 4.2 Execution Runtime Manager

Trusted component responsible for manipulating the selected isolation/runtime backend.

It owns runtime operations such as:

- create/start/inspect/stop/delete worker;
- create/remove isolated networks;
- attach approved mounts;
- apply resource limits;
- start Preview build/runtime services;
- return runtime liveness and exit facts.

It does not give runtime-control authority to autonomous workers.

The Runtime Manager may initially run in the same deployable service as the Run Coordinator if that keeps operations simple, but its privilege boundary must remain explicit in code.

## 4.3 Execution Worker

Disposable isolated environment for one Execution Attempt.

It can modify the canonical workspace only while the corresponding Project execution lease is valid.

## 4.4 Preview Runtime Group

One isolated group of generated-application services for one Preview source/configuration.

It is not the Execution Worker and does not contain the Siesta coding agent unless explicitly required by a future feature.

---

# 5. Initial Isolation Technology Decision

## 5.1 Hosted execution

Hosted Kallula **must use an OCI-compatible container isolation backend** or a stronger equivalent for:

- Execution Workers;
- untrusted Preview build processes;
- generated application services;
- supporting services.

The initial reference implementation should target a **rootless or user-namespace-isolated OCI runtime** where practical.

The exact product—such as a rootless Docker-compatible or Podman-compatible backend—is replaceable behind the Runtime Manager interface.

## 5.2 Why containers are the initial boundary

They provide a practical first implementation for:

- filesystem mounts;
- user namespaces;
- process isolation;
- resource limits;
- network namespaces;
- immutable images;
- reproducible runtime selection;
- disposable worker lifecycle.

This is not a claim that containers are a complete hostile-code sandbox.

The design therefore also requires:

- non-root execution;
- no privileged mode;
- no host network;
- no runtime socket inside workload containers;
- capability dropping;
- `no-new-privileges`;
- syscall/profile restrictions supported by the host;
- explicit mounts;
- network filtering;
- resource limits.

## 5.3 Development-only process mode

A direct host-process execution mode may exist **only** for explicitly marked local development.

It must:

- be disabled by default in production mode;
- show an insecure-development diagnostic;
- never be treated as equivalent to hosted isolation;
- not relax the normative production design.

**KEP-REQ-001** — Hosted execution must not run autonomous Project code directly as an unrestricted host process.

---

# 6. Runtime Manager Interface

The Runtime Manager is an architectural driver boundary, not necessarily a network microservice.

Conceptually it supports operations like:

```text
create_worker(spec)
inspect_worker(runtime_id)
signal_worker(runtime_id, signal/policy action)
stop_worker(runtime_id)
delete_worker(runtime_id)

create_network(spec)
delete_network(id)

create_preview_build(spec)
create_preview_service(spec)
inspect_service(id)
stop_service(id)
delete_service(id)

stream_logs(runtime_id/service_id)
```

The later API/Data Contract Specification will define internal contracts as needed.

The control plane must not expose raw container-runtime APIs to the browser.

---

# 7. Execution Host Model

## 7.1 Initial single-host model

A valid first hosted deployment may have:

```text
Host
├── Kallula Control Plane
├── Run Coordinator / Reconciler
├── Execution Runtime Manager
├── Control DB
├── durable workspace storage
├── durable Run Engine Runtime storage
├── OCI runtime
├── Preview Gateway
└── workload containers
```

Logical trust boundaries remain intact even when colocated.

## 7.2 Host users/permissions

Where the operating system/runtime supports it:

- control-plane service account;
- runtime-manager service account;
- workload container user namespaces;
- Preview gateway account;

should not all share unrestricted host filesystem permissions.

## 7.3 Future multi-host model

The architecture may later separate:

```text
Control host
Execution host A
Execution host B
Preview hosts
Shared/attachable durable storage
```

The Project/Run semantics do not change.

Only:

- Runtime Manager placement;
- workspace attachment;
- Run Engine Runtime attachment;
- Preview routing;

need alternate drivers.

---

# 8. Durable Storage Classes

Kallula distinguishes durable state from disposable runtime state.

## 8.1 Canonical Project Workspace — durable

Contains:

- source;
- `.git`;
- current working tree;
- engine-native per-project checkpoints;
- engine-native Project KB;
- native run evidence stored by the engine;
- generated tests;
- project-local configuration/artifacts that belong with the Project.

## 8.2 Run Engine Runtime — durable for Run retention

Contains mutable engine-adjacent state that must survive between Execution Attempts but is not canonical application source.

For current Siesta this may include Run-scoped copies/overlays of:

- mutable factory skills;
- Run-scoped global-learning graph/context;
- isolated Pi profile/state where persistence is required;
- adapter/runtime bookkeeping that must survive Attempt teardown.

It must not contain long-lived plaintext Kallula credentials.

## 8.3 Control-plane database — durable

Contains normalized product state and references.

## 8.4 Preview source snapshot — disposable/rebuildable

Immutable copy of a selected committed Project source state used to build/run a Preview.

## 8.5 Preview runtime data — disposable by default

Examples:

- installed dependencies;
- build artifacts;
- temporary databases;
- service writable layers.

It may persist while a Preview instance is alive, but is not part of Project durability unless a future feature explicitly promotes it.

## 8.6 Caches — disposable

Examples:

- package caches;
- compiler caches;
- image/build cache.

Loss must not corrupt product truth.

---

# 9. Canonical Workspace Physical Model

## 9.1 Stable identity

The workspace storage key/path uses Project ID, not display name or Siesta slug.

Conceptually:

```text
projects/<project-id>/workspace/
```

Exact root path is deployment configuration.

## 9.2 Ownership

The Workspace Manager owns:

- creation;
- attachment;
- validation;
- read/export;
- backup;
- cleanup after Project deletion policy.

## 9.3 Worker mount

During an active Execution Attempt:

```text
canonical workspace -> mounted read-write into worker
```

Only the worker holding the Project execution lease receives autonomous write access.

## 9.4 Control-plane access

Control Plane/Workspace Manager may read source for:

- Files UI;
- artifact indexing;
- Git metadata;
- export;
- Preview snapshot creation.

Direct mutation outside the execution lease remains deferred except for tightly controlled internal bookkeeping that cannot race engine work.

## 9.5 No workspace copy per Attempt

A resumed Attempt reattaches the same canonical workspace.

Kallula must not silently reconstruct the Project from the original prompt.

---

# 10. Workspace Mount Safety

## 10.1 Narrow mount

A worker receives only its target Project workspace.

It does not receive:

- projects root;
- other Projects;
- control-plane source;
- host home directory;
- credential store;
- host `/var/run` runtime socket.

## 10.2 Path validation

The Runtime Manager receives a Workspace Manager-approved canonical path/storage handle.

User-controlled strings never directly become arbitrary mount sources.

## 10.3 Symlinks

Mounting the workspace does not authorize following host-side symlinks outside the workspace for Kallula-managed browsing/export operations.

Workload execution may follow symlinks visible inside its own mount namespace, but must not thereby expose host files outside approved mounts.

---

# 11. Run Engine Runtime Physical Model

## 11.1 Identity

One logical Run has one Run Engine Runtime identity.

Conceptually:

```text
projects/<project-id>/runs/<run-id>/engine-runtime/
```

## 11.2 Lifetime

It survives:

- normal Execution Attempt exit;
- `WAITING_FOR_HUMAN`;
- safe stop;
- worker crash;
- worker restart;
- host restart within supported storage model.

## 11.3 Attempt attachment

Each Execution Attempt mounts the same Run Engine Runtime read-write where required.

## 11.4 Isolation

Run A never shares writable engine-learning state with Run B unless a future explicit promotion mechanism exists.

## 11.5 Immutable engine installation

The pinned Engine Installation is separate and mounted/read only.

This prevents self-learning from mutating the installed Siesta revision itself.

---

# 12. Engine Installation Physical Form

An Engine Installation consists conceptually of:

- immutable Siesta revision;
- Kallula adapter version;
- compatibility metadata;
- capability manifest;
- required Pi/tooling compatibility metadata;
- immutable bundled/adapted skills;
- integrity identity/digest.

It may be materialized as:

- immutable directory;
- package;
- OCI image layer;
- versioned artifact.

The runtime design requires only:

- read-only attachment;
- version identity;
- integrity verification;
- no Run-owned mutation.

---

# 13. Environment Profile and Environment Snapshot

## 13.1 Environment Profile

User/project reusable configuration describing desired execution capabilities.

Examples:

- Auto;
- Python;
- Node;
- Python + Node;
- additional supporting services;
- resource policy;
- network policy.

## 13.2 Environment Snapshot

A Run receives an immutable resolved Environment Snapshot.

It identifies:

- execution image digest;
- OS/base runtime identity;
- language/runtime versions;
- installed Kallula/engine prerequisites;
- resource limits;
- network policy;
- supporting service definitions;
- package-manager policy;
- Preview/runtime pack compatibility;
- runtime-plan version.

Changing Project defaults does not mutate an existing Run snapshot.

## 13.3 Auto resolution

`Auto` resolves before actual engine execution requires the environment.

Resolution may use:

- original request;
- imported repository metadata;
- detected project files;
- engine-produced specification where available;
- supported runtime packs.

The resolver must choose from supported capabilities rather than invent host configuration dynamically.

---

# 14. Curated Runtime Packs

The initial hosted product should prefer **curated runtime packs** over arbitrary host provisioning.

A runtime pack may provide:

- immutable OCI image;
- language runtimes;
- Git;
- build essentials;
- Pi/runtime prerequisites;
- common package managers;
- Kallula runtime helper;
- supported architecture metadata.

Examples may eventually include:

- Python;
- Node.js;
- Python + Node.js;
- Go;
- other packs based on actual product demand.

This document does not need all packs in v1.

## 14.1 Why curated packs

They reduce:

- privileged system-package installation;
- host mutation;
- drift;
- hard-to-reproduce setup.

## 14.2 System packages

Arbitrary host package installation by agents is not permitted.

A worker may install Project-language dependencies within its sandbox.

Additional OS-level packages require:

- a supported runtime pack;
- a validated environment extension/build mechanism;
- or future explicit custom-environment support.

---

# 15. Worker Image Composition

A Worker is formed from:

```text
resolved Environment Image
  +
read-only Engine Installation
  +
read-write canonical Workspace
  +
read-write Run Engine Runtime
  +
ephemeral scratch/home/tmp/cache mounts
  +
explicit environment variables
  +
isolated network policy
```

This separation allows:

- Siesta upgrades without redefining Project storage;
- environment upgrades without mutating source;
- Attempt recreation without losing Run state.

---

# 16. Worker Runtime Hardening

Hosted worker containers must use:

- non-root workload user;
- no privileged mode;
- no host network;
- no host PID namespace;
- no host IPC namespace;
- no runtime/Docker/Podman socket;
- dropped Linux capabilities by default;
- `no-new-privileges`;
- runtime default or stricter seccomp/profile restrictions;
- bounded process count;
- bounded CPU;
- bounded memory;
- bounded temporary storage where supported;
- explicit mounts only.

Writable paths should be limited to:

- canonical workspace;
- Run Engine Runtime;
- bounded scratch/home/tmp/cache.

The container root filesystem should be read-only where the selected runtime pack supports it.

---

# 17. Execution Attempt Lifecycle

A normal Attempt lifecycle is:

```text
durable start/resume command accepted
    ↓
acquire Project execution lease
    ↓
resolve pinned Engine + Environment Snapshot
    ↓
validate workspace and Run Engine Runtime
    ↓
create Attempt record
    ↓
create worker runtime
    ↓
attach mounts/network/resources
    ↓
start adapter/Siesta
    ↓
emit/ingest events + heartbeat/liveness
    ↓
semantic outcome
    ↓
persist outcome/evidence
    ↓
stop/delete worker
    ↓
reconcile workspace
    ↓
release lease when safe
```

The worker container is not the Run.

---

# 18. Worker Entry Process

The initial container entry process should be a small trusted Kallula worker bootstrap that:

1. validates required immutable identifiers;
2. verifies expected mounts exist;
3. constructs the narrow child environment;
4. launches the Kallula Siesta adapter;
5. forwards structured events/outcomes through the defined adapter channel;
6. captures process exit facts;
7. exits.

It must not become an alternative orchestration engine.

Siesta remains responsible for software-factory workflow.

---

# 19. Heartbeat and Liveness

## 19.1 Runtime liveness

The Runtime Manager can observe container/runtime existence and exit state.

## 19.2 Attempt heartbeat

Kallula maintains an Attempt heartbeat/lease renewal signal independent of browser connectivity.

The heartbeat may be produced by:

- Runtime Manager observation;
- trusted worker bootstrap;
- both.

## 19.3 Lease rule

Liveness evidence supports lease renewal.

Lease expiry still triggers reconciliation; it is not proof of safe worker death.

---

# 20. Attempt Termination Classes

The Runtime Manager should distinguish at least:

- normal semantic engine outcome;
- requested runtime termination;
- process non-zero exit;
- timeout;
- out-of-memory termination where observable;
- host/runtime lost;
- policy/security termination;
- unknown exit.

These facts feed normalized failure classification.

A raw exit code alone does not determine Run completion.

---

# 21. Waiting for Human

When the adapter produces a durable pending interaction:

1. interaction/event state is persisted;
2. engine state/transcript/checkpoint is durable;
3. Attempt ends with semantic `WAITING_FOR_HUMAN`;
4. worker container is deleted;
5. canonical workspace remains;
6. Run Engine Runtime remains;
7. execution lease is released after reconciliation;
8. Run remains `WAITING_FOR_HUMAN`.

When the user answers:

- same Run continues;
- new Execution Attempt attaches to the same workspace/runtime.

No idle worker must remain alive waiting on browser input.

---

# 22. Safe Stop

The stop flow follows the architecture and engine adaptation semantics.

## 22.1 Request

A durable stop command changes Run control state to `STOP_REQUESTED`.

## 22.2 Runtime behavior

The Runtime Manager does **not** immediately kill the container for a normal safe stop.

The adapter translates the request into the engine-supported cooperative mechanism.

For current Siesta this may become a native stop marker at a safe boundary.

## 22.3 Completion

Only engine/adapter confirmation plus reconciliation produces `STOPPED`.

## 22.4 Emergency termination

A separate operator/security emergency termination capability may hard-stop a worker.

It must not be presented as a normal safe stop and may leave the Run failed/uncertain.

---

# 23. Resume and Recreate

Resume creates a new Execution Attempt, not a new worker continuation.

The old worker is never required.

Resume:

- validates pinned engine/adapter compatibility;
- validates Environment Snapshot availability;
- reattaches canonical workspace;
- reattaches Run Engine Runtime;
- creates fresh scratch/runtime container;
- continues the same logical Run.

If the exact required environment image or engine installation is unavailable, resume fails closed unless validated migration policy exists.

---

# 24. Dependency Installation

Dependency installation executes untrusted third-party code.

It therefore occurs inside the worker/Preview build sandbox.

## 24.1 Language dependencies

Allowed through supported package managers inside the sandbox.

## 24.2 Global host mutation

Forbidden.

## 24.3 Caches

Package caches may use disposable/cache volumes.

Caches:

- are not authoritative;
- may be deleted at any time;
- must not contain Kallula-managed plaintext credentials;
- should be keyed/scoped to prevent cross-user/Project data leakage.

## 24.4 Lockfiles

Existing lockfiles should be respected when supported by project tooling.

Kallula does not silently rewrite dependency versions solely to make installation easier.

---

# 25. Build and Test Commands

Coding-agent commands run inside the Execution Worker.

They inherit:

- worker resource limits;
- worker network policy;
- worker filesystem mounts;
- narrow environment.

They do not inherit:

- Preview runtime credentials;
- GitHub authority;
- control-plane credentials.

A Project can therefore build/test without becoming a privileged platform process.

---

# 26. Resource Governance

Every hosted workload must have finite limits.

## 26.1 Worker limits

Environment Snapshot includes policy for:

- CPU;
- memory;
- PIDs/process count;
- Attempt wall-clock duration;
- temporary/scratch storage;
- optional I/O constraints.

## 26.2 Preview limits

Preview services have separate limits from coding workers.

A runaway generated application must not consume the worker/control plane budget indefinitely.

## 26.3 Supporting service limits

Database/cache services also require bounded resources.

## 26.4 Exact values

The first deployment may use platform defaults.

Hard numeric defaults belong in deployment/configuration documentation and can evolve without changing this specification.

---

# 27. Network Zones

The runtime uses explicit network zones.

Conceptually:

```text
Control Network
  Control Plane / DB / Credential boundary

Execution Network
  Worker
  -> allowed external destinations
  X control privileged endpoints

Preview Project Network
  App services <-> supporting services
  -> policy-controlled public egress
  X control privileged endpoints
  X other Project networks

Preview Ingress
  Preview Gateway -> explicitly public Preview service
```

---

# 28. Worker Network Policy

A worker may need public internet for:

- package registries;
- source documentation/tools permitted by future features;
- model/provider access where not brokered.

It must not gain access to internal privileged services merely because they are routable.

At minimum, runtime policy denies:

- control DB;
- credential/key service;
- runtime-manager administration interface;
- host management interfaces;
- cloud/instance metadata addresses;
- other Projects' private networks.

The Environment Snapshot can define stronger modes such as:

```text
none
public-internet
restricted-allowlist
```

The exact firewall technology is replaceable.

---

# 29. Preview Network Policy

Preview services communicate on an isolated per-Preview or per-Project Preview network.

They may reach:

- declared services in the same Preview group;
- public internet if Environment/Preview policy allows.

They may not reach:

- Kallula control network;
- credential service;
- host/runtime APIs;
- other Project Preview networks;
- instance metadata endpoints.

Public egress does not make runtime secrets safe from malicious application code. Secret injection therefore remains explicit user authorization.

---

# 30. Supporting Services

Generated applications may require services such as:

- PostgreSQL;
- Redis;
- object-storage emulator;
- other supported development dependencies.

## 30.1 Kallula-managed service definitions

The initial product should use curated supporting-service definitions/images pinned by digest.

## 30.2 No arbitrary privileged Compose

Kallula does not initially execute arbitrary repository `docker-compose.yml` with unrestricted semantics.

A Compose file may eventually be inspected as a hint, but host mounts, privileged mode, host networking, runtime sockets, device mappings, and arbitrary capabilities must not be accepted automatically.

## 30.3 Service credentials

Development-service credentials generated by Kallula may be ephemeral Preview/runtime secrets.

They are scoped to the Preview group and are not Project long-lived credentials unless deliberately promoted.

---

# 31. Runtime Plan

A **Runtime Plan** describes how to build/run the generated application.

It is Kallula normalized data.

It may contain:

- source identity;
- Environment Snapshot;
- application services;
- supporting services;
- working directories;
- build commands;
- start commands;
- internal ports;
- public service routes;
- health checks;
- service dependencies;
- runtime credential aliases;
- network policy;
- resource policy.

## 31.1 Authority

A Runtime Plan can be produced from:

- deterministic project inspection;
- supported framework metadata;
- engine/agent hints;
- user override.

Agent-provided hints are untrusted proposals until validated by Kallula.

## 31.2 Storage

The authoritative Runtime Plan is stored as Kallula control state/versioned configuration.

It is not required to live as editable source inside the repository.

## 31.3 Reproducibility

A Preview records the exact Runtime Plan version/snapshot used.

---

# 32. Runtime Detection

`Auto` runtime detection should be conservative.

Possible signals include:

- `pyproject.toml`;
- `requirements.txt`;
- `package.json`;
- framework configuration;
- known entry files;
- existing documented start commands;
- engine-provided structured hints.

Detection may propose:

- runtime pack;
- build command;
- start command;
- port;
- health path.

If confidence is insufficient, Preview becomes **Not runnable / configuration required** rather than executing arbitrary guesses repeatedly.

---

# 33. User-Provided Runtime Configuration

Advanced users may override supported Runtime Plan fields.

Overrides remain constrained by security policy.

They cannot request:

- host mounts;
- privileged container;
- host network;
- runtime socket;
- access to control-plane secrets.

Changing runtime configuration creates a new effective Runtime Plan version.

---

# 34. Separation of Preview Build and Runtime

Preview uses two phases:

```text
stable source snapshot
    ↓
isolated Preview Build
    ↓
runnable build output / prepared source
    ↓
generated application runtime
```

## 34.1 Build phase

The build phase:

- runs without Project runtime secrets by default;
- may use public package-network access;
- uses bounded resources;
- may execute untrusted package/build scripts;
- cannot access Kallula control authority.

## 34.2 Runtime phase

The runtime phase:

- receives only Runtime Plan-declared assigned Project credentials;
- starts application service processes;
- receives Preview network access;
- emits runtime logs;
- has no coding-agent/Siesta process.

This separation must prevent a build tool or coding agent from receiving application secrets simply because the running app needs them.

---

# 35. Preview Source Identity

A Preview never runs directly against a live mutable workspace mount.

It runs from a **stable source snapshot**.

## 35.1 Preferred source

For Git-backed Projects the preferred Preview source is an exact commit.

Examples:

- latest current committed state;
- exact Verified State commit;
- selected historical Run commit.

## 35.2 Dirty workspace

If the canonical workspace contains uncommitted changes, those changes are not silently included in the Preview.

The initial product should prefer:

```text
Preview source: latest committed Project state
Current workspace: additional uncommitted changes exist
```

A future explicit content-snapshot feature may Preview dirty state if it can create an immutable content identity safely.

## 35.3 Why this rule exists

It prevents:

- source changing while application builds;
- inconsistent multi-file reads;
- Preview running half-written files;
- confusion over what the browser is actually showing;
- write access from Preview back into canonical source.

---

# 36. Preview Source Snapshot Creation

For a Git commit, Kallula may create a temporary Preview source tree using safe Git mechanisms.

Properties:

- immutable to the build/runtime process except copied build scratch;
- no `.git` credentials;
- no Kallula secret material;
- source identity recorded;
- disposable after Preview teardown/rebuild.

The exact Git worktree/archive/snapshot mechanism is an implementation choice.

---

# 37. Preview Instance Model

A Preview Instance has at least:

- Preview ID;
- Project ID;
- optional originating Run ID;
- source identity/commit;
- Runtime Plan version;
- Environment/Preview runtime identity;
- credential assignment/value-version metadata without plaintext;
- state;
- created/started/stopped timestamps;
- route identity;
- health summary;
- service records;
- log references;
- failure summary.

A Preview Instance is not a Verified State.

---

# 38. Preview Lifecycle

Normalized Preview states remain:

```text
NOT_RUNNABLE
STARTING
AVAILABLE
UNAVAILABLE
FAILED
STOPPED
```

A detailed internal lifecycle may include:

```text
REQUESTED
SNAPSHOTTING
BUILDING
STARTING_SERVICES
HEALTH_CHECKING
AVAILABLE
STOPPING
STOPPED
FAILED
```

The UX may project these into simpler labels.

---

# 39. Preview Start Flow

```text
Committed source
      |
      v
Immutable source snapshot
      |
      v
Preview build
(no Project runtime secrets by default)
      |
      v
Application runtime
(only assigned service secrets)
      |
      v
Health check
      |
      v
Preview Gateway
      |
      v
Browser
```


```text
user requests Preview
    ↓
authorize Project/Preview action
    ↓
choose exact source commit
    ↓
resolve Runtime Plan
    ↓
create Preview record
    ↓
create immutable source snapshot
    ↓
create isolated Preview network
    ↓
start supporting services
    ↓
run build phase
    ↓
request only declared runtime credentials
    ↓
start application services
    ↓
run health checks
    ↓
register Preview Gateway route
    ↓
AVAILABLE
```

If a step fails:

- preserve failure/log evidence;
- clean up unsafe/partial runtime resources;
- mark Preview `FAILED`.

---

# 40. Preview Stop Flow

```text
stop Preview requested
    ↓
remove/disable ingress route
    ↓
terminate application services
    ↓
terminate supporting services
    ↓
revoke/drop ephemeral runtime grants
    ↓
delete Preview network
    ↓
delete disposable source/build/runtime volumes
    ↓
STOPPED
```

Stopping Preview never modifies canonical Project source.

---

# 41. Preview Update Behavior

A running Preview is pinned to its source identity.

If a newer Project commit appears:

- existing Preview remains on old source;
- UI marks it out of date where relevant;
- user may request **Update Preview** or restart;
- Kallula creates/rebuilds from the new selected source.

The initial product should not silently hot-reload a Preview across autonomous source changes unless a future explicit development mode defines that behavior.

---

# 42. Preview Routing

## 42.1 Gateway

All hosted Preview browser access goes through a Kallula-controlled Preview Gateway.

Raw workload ports are not exposed directly to the public network.

## 42.2 Routing key

Routing uses an opaque Preview/service identity, not user-controlled hostnames.

## 42.3 TLS

Hosted Preview ingress uses HTTPS.

## 42.4 Multiple services

A Runtime Plan may designate:

- one primary public service;
- additional explicitly public services/routes;
- private supporting services.

The gateway exposes only declared public services.

## 42.5 WebSockets

The gateway should support WebSocket upgrade for declared Preview routes when the chosen frontend/runtime requires it.

This does not grant access to Kallula control WebSockets/APIs.

---

# 43. Preview Origin Strategy

Hosted production Preview must use a security boundary that does not receive Kallula control-plane cookies.

The preferred production design is a **separate registrable domain/site** for Preview.

Conceptually:

```text
Control Plane:
app.<kallula-control-domain>

Preview:
<opaque-preview-id>.<separate-preview-domain>
```

The exact domains are deployment configuration.

Control-plane cookies remain host-only and are never scoped to the Preview domain.

Local development may use localhost/random ports with explicit development-mode limitations.

---

# 44. Preview Access Authorization

Preview may be private even though it is browser-reachable.

## 44.1 Control-plane authorization

The user first authorizes access through Kallula.

## 44.2 Preview access grant

Kallula may issue a short-lived, Preview-scoped access grant to the Preview Gateway.

Preferred flow:

```text
Authenticated Kallula user
    ↓
Open Preview
    ↓
short-lived one-time/limited grant
    ↓
Preview Gateway validates/exchanges grant
    ↓
Preview-domain access session
    ↓
generated application
```

## 44.3 Separation

The generated application never receives the Kallula control-plane session cookie.

Preview access credentials:

- are scoped to a Preview;
- are short-lived or revocable;
- are not reusable as control-plane API authority.

Exact token/cookie format belongs to the API/security implementation.

---

# 45. Runtime Secret Injection

Project runtime credentials are injected **only** into declared application services that require them.

## 45.1 Secret resolution

The Runtime Manager receives authorized secret material from the trusted credential boundary only after:

- Project assignment validation;
- Preview/service policy validation;
- user/Run authorization as required.

## 45.2 Injection target

Secret values are passed to the target application process through a supported runtime mechanism such as:

- environment variables scoped to that service;
- in-memory file/FD mechanism;
- runtime-specific secret mount.

## 45.3 Forbidden persistence

Kallula must not write runtime secrets into:

- Preview source snapshot;
- canonical workspace;
- `.env` file in source;
- Git;
- Runtime Plan plaintext;
- build logs;
- command arguments where avoidable.

## 45.4 Build separation

Preview build containers receive no Project runtime secrets by default.

## 45.5 Service scoping

If only backend service `api` requires `STRIPE_SECRET_KEY`, frontend service `web` does not receive it.

---

# 46. Preview Credential Rotation

If an assigned credential value changes while Preview is running:

- existing application process may still hold the old value;
- Preview is marked/reported as requiring restart for the new value;
- restart uses the new authorized value;
- old plaintext is not retained by Kallula beyond process lifetime.

Automatic rolling restart is not required initially.

---

# 47. Application Service Supervision

Each Preview application service is supervised by the Runtime Manager/runtime backend.

Kallula records:

- runtime service ID;
- start time;
- restart count if restart policy exists;
- exit code/reason;
- health;
- logs.

## 47.1 Restart policy

Initial default should be conservative.

A service may receive a small bounded automatic restart count for transient crashes.

Infinite restart loops are prohibited.

Repeated failure becomes Preview `FAILED` or `UNAVAILABLE` with evidence.

---

# 48. Supporting Service Data

Preview databases/caches are **development Preview state**.

Initial semantics:

- may use named disposable volumes for the lifetime of a Preview Instance;
- can survive an individual application-service restart;
- are deleted when Preview is fully destroyed unless explicitly retained by a future feature;
- are not part of canonical source or Verified State;
- are not guaranteed backup data.

The UX should not imply production durability.

---

# 49. Health Checks

A service can become `AVAILABLE` only after its configured health condition passes.

Supported conceptual checks:

- TCP port accepting connections;
- HTTP endpoint returning acceptable status;
- process alive for startup grace period when no better health probe exists.

A process merely existing is weaker evidence than an application health check.

The Runtime Plan records the check.

---

# 50. Preview Startup Timeouts

Every startup/build/health phase is bounded.

Timeouts are explicit runtime policy.

On timeout:

- stop affected resources;
- preserve bounded logs/evidence;
- mark Preview failed with timeout class;
- do not leave indefinite hidden processes running.

---

# 51. Runtime Logs

## 51.1 Sources

Kallula captures:

- Preview build stdout/stderr;
- application service stdout/stderr;
- supporting-service logs where useful.

## 51.2 Association

Every log stream is associated with:

- Preview ID;
- service/build phase;
- runtime instance;
- time range.

## 51.3 Redaction

Security-design redaction occurs before persistent user-visible storage for controlled log channels.

## 51.4 Streaming

Live log viewing may use a streaming transport, but durable bounded history remains available after browser disconnect.

## 51.5 Retention

Exact retention is deployment policy.

Logs are not canonical Project source.

---

# 52. Worker Logs and Engine Evidence

Worker process logs are separate from normalized Activity.

They may include:

- bootstrap diagnostics;
- container/runtime facts;
- adapter diagnostics;
- Pi/provider stderr.

They must:

- pass through security redaction;
- remain attributable to Execution Attempt;
- not substitute for normalized state;
- be bounded/retained according to policy.

Native engine artifacts remain in their authoritative workspace/runtime locations and are indexed separately.

---

# 53. Artifact and Source Boundaries

Runtime-generated data is classified.

## Canonical Project source

May be exported/published.

## Engine-native Project state/evidence

Retained for resume/provenance but may be excluded from clean source export according to adapter rules.

## Run Engine Runtime

Not part of Project source export.

## Preview build output

Disposable/rebuildable.

## Preview databases/runtime state

Disposable development state.

## Logs

Observable evidence; not source.

The Workspace Manager/Artifact Index must preserve these distinctions.

---

# 54. Preview vs Verification

Preview startup and health are independent from verification.

A Preview may be:

```text
AVAILABLE
```

while the source is:

```text
UNVERIFIED
```

Likewise, a Verified State may exist even if no Preview is currently running.

Preview health must never update a Verified State automatically.

If the engine's verification process performs its own runtime smoke test, that evidence is recorded through the engine/verification path, not by reinterpreting Preview status.

---

# 55. Runtime Failure Classification

Useful normalized runtime failure classes include:

```text
WORKER_START_FAILED
WORKER_EXITED
WORKER_TIMEOUT
WORKER_OOM
WORKER_LOST
RUNTIME_POLICY_DENIED
WORKSPACE_ATTACH_FAILED
ENGINE_RUNTIME_ATTACH_FAILED
ENVIRONMENT_UNAVAILABLE
DEPENDENCY_INSTALL_FAILED

PREVIEW_SNAPSHOT_FAILED
PREVIEW_BUILD_FAILED
PREVIEW_SERVICE_START_FAILED
PREVIEW_HEALTH_FAILED
PREVIEW_TIMEOUT
PREVIEW_ROUTE_FAILED
PREVIEW_RUNTIME_OOM
PREVIEW_RUNTIME_LOST
SUPPORTING_SERVICE_FAILED
```

Exact enums belong to the API/Data Contract Specification.

---

# 56. Crash Recovery — Execution Worker

On coordinator/runtime-manager restart:

1. inspect Runs that claim active Attempts;
2. inspect lease records;
3. query runtime backend for containers labelled with Kallula identity;
4. inspect Attempt runtime identity;
5. inspect workspace/engine checkpoint evidence;
6. reconcile.

Possible outcomes:

- worker still alive -> continue observation;
- worker exited with known semantic outcome -> finalize Attempt;
- worker lost -> mark Attempt lost and Run failed/resumable as appropriate;
- durable pending interaction exists -> restore `WAITING_FOR_HUMAN`;
- confirmed safe stop exists -> restore `STOPPED`;
- engine completed -> finalize product state;
- uncertain -> fail closed/reconciliation-required.

The Runtime Manager must never start a second writable worker merely because it cannot immediately see the first.

---

# 57. Crash Recovery — Runtime Manager/Host

## 57.1 Runtime manager restart

Containers may outlive the manager.

The manager reconstructs runtime ownership from:

- durable Attempt/Preview records;
- runtime labels/metadata;
- container/network/volume inventory.

## 57.2 Host restart

After host boot:

- durable workspace remains;
- Run Engine Runtime remains;
- ephemeral workers/previews may be gone;
- reconciler determines Runs needing resume/failure state;
- Preview records become stopped/unavailable/failed based on actual runtime recovery policy.

Initial Preview workloads are not required to auto-restart after host reboot unless explicitly configured.

## 57.3 Orphan cleanup

Unknown runtime resources are not immediately deleted.

They are matched against durable Kallula identity first.

Only confirmed orphan resources are cleaned.

---

# 58. Runtime Labels and Identity

Every workload resource created by Kallula should include safe non-secret metadata/labels such as:

- Kallula managed=true;
- Project ID;
- Run ID when applicable;
- Execution Attempt ID;
- Preview ID;
- service name;
- Environment Snapshot ID;
- Engine Installation ID where applicable.

Labels must not contain:

- secret values;
- user prompts/source;
- credentials;
- sensitive personal data.

These labels support reconciliation and orphan cleanup.

---

# 59. Cleanup Rules

## 59.1 Attempt completion

Delete:

- worker container;
- ephemeral scratch/tmp;
- Attempt-only network resources.

Retain:

- canonical workspace;
- Run Engine Runtime;
- durable logs/events/artifacts per retention;
- cache volumes only if policy permits.

## 59.2 Preview stop/delete

Delete:

- ingress mapping;
- app/support service containers;
- Preview network;
- Preview source snapshot;
- build scratch;
- disposable Preview data volumes according to policy.

Retain:

- Preview record;
- logs/evidence according to retention;
- source identity/Runtime Plan identity.

## 59.3 Never during routine cleanup

Do not delete:

- canonical Project workspace;
- `.git`;
- active Run Engine Runtime;
- credential records;
- Verified State evidence.

---

# 60. Disk Pressure and Quotas

The platform must protect the host from unbounded Project execution.

Categories subject to quota/cleanup policy include:

- workspace size;
- Run Engine Runtime size;
- package/build caches;
- worker scratch;
- Preview build output;
- Preview volumes;
- logs.

When limits are reached:

- fail the affected operation clearly;
- do not delete canonical source automatically to recover space;
- cache cleanup may be automatic;
- destructive Project cleanup requires explicit policy/user action.

---

# 61. Workspace Backup Consistency

Backups of a writable workspace must not silently capture an inconsistent multi-file state.

Initial acceptable approaches include:

- backup when Project has no active write lease;
- storage-level snapshot that is atomic enough for the selected filesystem;
- coordinated quiescence.

Exact backup tooling is open.

Git history alone is not a complete backup of:

- uncommitted current work;
- engine checkpoints;
- native KB/evidence.

Run Engine Runtime backup must be coordinated when it is required for resumability.

---

# 62. Environment Changes Across Runs

Project default Environment Profile changes affect future Runs.

An existing Run remains pinned to its Environment Snapshot.

If a stopped Run's exact environment is unavailable:

- resume compatibility fails;
- Kallula does not silently resolve a new environment;
- migration requires explicit compatibility policy.

This mirrors Engine Installation pinning.

---

# 63. Runtime Image Lifecycle

Runtime images are identified by immutable digest where supported.

## 63.1 New Run

May use the latest supported image that satisfies the selected Environment Profile.

## 63.2 Existing Run

Uses the pinned image digest/Environment Snapshot.

## 63.3 Vulnerability retirement

If an image must be revoked for security reasons:

- it can be marked unsupported;
- new Runs cannot use it;
- resumability of pinned Runs may become security-blocked;
- migration is explicit.

Security overrides convenience.

---

# 64. Application Runtime Image Strategy

Preview application execution should initially use trusted Kallula runtime packs rather than allowing generated code to control host/container privileges.

A Runtime Plan executes:

- Project build commands;
- Project start commands;

inside those constrained images.

Direct execution of arbitrary user-provided Dockerfiles/Compose as privileged infrastructure is deferred.

Future Dockerfile support must preserve:

- rootless/isolated build;
- no host runtime socket;
- no privileged mounts/capabilities;
- output image scanning/policy;
- same Preview network/secret constraints.

---

# 65. Multi-Service Applications

The runtime model supports multi-service applications conceptually from the start.

Example:

```text
Preview Group
├── web      public
├── api      optionally public/path-routed
├── worker   private
├── postgres private supporting service
└── redis    private supporting service
```

Services communicate through runtime DNS/service aliases on the isolated Preview network.

Only explicitly public services receive gateway routes.

This avoids redesigning Preview once Kallula builds more than single-process apps.

---

# 66. Service Dependencies and Startup Order

Runtime Plan may express:

- dependency relationships;
- readiness conditions;
- startup ordering.

Example:

```text
postgres healthy
    ↓
api starts
    ↓
api healthy
    ↓
web starts
```

Kallula should use readiness, not fixed sleeps, where practical.

Circular/invalid dependencies fail plan validation.

---

# 67. Runtime Environment Variables

Non-secret environment values may include:

- service ports;
- service DNS names;
- development database URLs using ephemeral credentials;
- `KALLULA_PREVIEW=true` or equivalent application-mode signal where useful;
- user-declared configuration.

Secret values remain governed by the Credential Design.

Runtime Plan persists non-secret values and secret aliases separately.

---

# 68. Port Model

Application services bind to internal container/network ports.

Kallula must not require projects to bind fixed public host ports.

The Runtime Manager/gateway maps Preview routes to internal service endpoints.

Port collisions therefore do not become global Project conflicts.

`localhost` inside one service refers to that service container, not supporting services; service DNS aliases are used for cross-service communication.

---

# 69. Preview Route Stability

A Preview Instance should have a stable route while it remains active.

Updating/rebuilding may either:

- preserve the route while swapping backend instance safely;
- or create a new Preview Instance/route.

The initial implementation may choose the simpler explicit restart model.

Route identity must not be derived from mutable Project names alone.

---

# 70. Preview Access Lifetime

Preview access is bounded independently from application process lifetime.

The platform may support:

- owner-only Preview;
- time-bounded Preview access;
- manually stopped Preview.

Public unauthenticated sharing is not required initially.

If later added, it requires explicit sharing policy because generated applications are untrusted.

---

# 71. Browser/API Isolation

Preview JavaScript must not be able to treat its Preview-domain credentials as Kallula API credentials.

Therefore:

- Preview access session differs from Kallula session;
- Preview origin is not an authenticated control API CORS origin by default;
- control-plane APIs enforce normal authenticated origin/session policy.

This implements the Security Design's browser trust boundary.

---

# 72. Runtime Log Backpressure

A malicious/noisy service can produce unbounded stdout.

The runtime must apply:

- bounded in-memory buffering;
- log size/rate limits;
- truncation/drop indicators;
- retention limits.

Dropping excessive logs must not terminate authoritative Run/Preview state silently.

The UI should know when logs were truncated.

---

# 73. Process Output and Encoding

Runtime capture must handle:

- stdout;
- stderr;
- partial lines;
- non-UTF-8 bytes.

Binary/invalid data is safely encoded/replaced for log display.

It must not crash the supervisor or bypass redaction merely because output is malformed.

---

# 74. Time and Clock Assumptions

Runtime timestamps are metadata, not global ordering authority.

Attempt/Preview lifecycle uses durable state transitions and IDs.

Container clock differences must not be used to decide lease ownership or event order.

---

# 75. Runtime Policy Validation Before Launch

Before creating a workload, the Runtime Manager validates the resolved specification.

Reject:

- host network;
- privileged mode;
- forbidden capabilities;
- unapproved mounts;
- runtime socket mounts;
- control-plane network attachment;
- invalid source path;
- unavailable image digest;
- resource policy outside platform bounds;
- unauthorized secret alias;
- unsupported service exposure.

This validation occurs server-side even if UI already restricts fields.

---

# 76. Environment and Runtime Compatibility

A Run can start only if:

```text
Engine Installation
    compatible with
Environment Snapshot
    compatible with
runtime backend/host architecture
```

Examples of compatibility dimensions:

- CPU architecture;
- required Pi executable/runtime;
- language toolchain;
- filesystem/mount expectations;
- security mode;
- network capability.

Compatibility is checked before worker launch.

---

# 77. Preview Compatibility

Preview source is runnable only if Kallula can resolve:

- supported Runtime Plan;
- suitable Preview runtime pack;
- valid public service route;
- required supporting services;
- required credential assignments;
- security-compliant network/resource policy.

Otherwise Preview state is `NOT_RUNNABLE` with actionable explanation.

---

# 78. Observability

Runtime observability includes safe metadata for:

- worker create/start/stop duration;
- image pull/build duration;
- CPU/memory utilization;
- OOM/policy termination;
- Preview build/start/health duration;
- service restarts;
- cache/storage usage;
- runtime errors.

Telemetry must obey the Security Design:

- no secrets;
- no full prompts/source by default;
- bounded cardinality.

---

# 79. Local Development Experience

Local development should preserve product semantics while permitting simpler infrastructure.

A recommended local mode may use:

- local database;
- local durable workspace directory;
- local OCI runtime;
- local Preview gateway;
- localhost-based Preview routes.

Developers may enable direct-process mode only with explicit insecure configuration.

Tests must cover the containerized/production-equivalent path; development convenience cannot become the only tested runtime.

---

# 80. Portability Boundary

Kallula core code should depend on:

- Workspace Manager;
- Runtime Manager;
- Preview Gateway/Controller;
- Environment Resolver;

not on scattered Docker/Podman CLI calls.

The first runtime driver can be OCI-container-specific.

This is justified abstraction because the product explicitly requires:

- isolated workloads;
- disposable workers;
- future multi-host viability.

It is not a generic plugin marketplace.

---

# 81. Multi-Host Evolution Path

A future multi-host design may replace:

```text
local bind mount
```

with:

```text
attachable volume / replicated workspace / controlled sync
```

and replace local runtime calls with remote execution-host commands.

The following remain unchanged:

- one Project write lease;
- one canonical workspace identity;
- Run/Attempt distinction;
- pinned Engine/Environment Snapshot;
- Preview source identity;
- credential policy;
- normalized events/state.

Kallula should not implement multi-host scheduling before required by load.

---

# 82. Concurrency Rules

## 82.1 Project worker

At most one autonomous worker may hold write ownership of a Project workspace.

## 82.2 Preview

A Preview can run concurrently with a coding worker because it uses an immutable source snapshot, not the writable workspace.

## 82.3 Multiple Previews

Multiple Preview Instances from different commits/configurations may exist in the future.

The first release may limit one active Preview per Project for simplicity without changing the model.

## 82.4 Files UI/export

Read operations can occur while worker writes, but source export should use Git commit/snapshot semantics where consistency matters.

---

# 83. Preview During Active Run

During an active Run, Preview may be started from the latest eligible committed source.

If current workspace has newer dirty changes:

- those changes are not included;
- UI states this clearly.

When Siesta creates a newer commit:

- current Preview remains pinned;
- UI may offer update/restart.

No read-lock on the live workspace is required for the duration of Preview.

---

# 84. Verified State Preview

The user may request a Preview of the last Verified State.

That Preview:

- uses the exact verified commit;
- records that source identity;
- is still a development Preview, not production deployment;
- may fail to start due to environmental drift even though verification previously passed.

A Preview failure does not invalidate historical verification evidence.

---

# 85. Existing Repository Runtime Behavior

Imported repositories use the same runtime model.

Kallula does not grant imported project configuration authority over host infrastructure.

Repository files may inform Runtime Plan detection but cannot automatically request:

- host mounts;
- privileged containers;
- control network access;
- platform credentials.

---

# 86. Runtime Policy for Agent-Created Configuration

If the coding agent writes:

- `.env`;
- Dockerfile;
- Compose file;
- shell scripts;
- CI config;

those files remain ordinary untrusted Project source.

Kallula may inspect them, but runtime authority comes from validated Kallula Environment/Runtime Plan configuration.

This prevents generated infrastructure files from bypassing platform policy.

---

# 87. Preview and Generated Frontend URLs

Generated applications should receive stable service URLs through runtime configuration rather than hard-coded host container addresses.

Examples:

- frontend receives Preview API route as non-secret configuration;
- backend receives internal database DNS URL;
- browser receives gateway URL.

Exact URL-injection mechanism depends on framework/runtime pack.

---

# 88. CORS Inside Generated Applications

Kallula cannot automatically guarantee that arbitrary generated backends allow the generated frontend origin correctly.

Runtime Plan may provide the app with its externally visible Preview origin as non-secret configuration.

The agent can use it when building application CORS settings.

Preview Gateway must not bypass the generated application's own application-level authorization/CORS by proxying requests as trusted control-plane calls.

---

# 89. Runtime Secret Names

The Runtime Plan references credential aliases/IDs, not values.

Example:

```text
service: api
secrets:
  STRIPE_SECRET_KEY -> credential-id-123
```

At launch:

```text
trusted resolver
    ↓
authorization
    ↓
decrypt
    ↓
target service only
```

The resolved value never becomes part of the stored Runtime Plan.

---

# 90. Preview Build Reuse

Build output may be cached by a key including:

- source commit;
- Runtime Plan version;
- runtime image digest;
- relevant non-secret build configuration.

Caches must not key on or store plaintext runtime secrets.

Because build runs without Project runtime secrets by default, build artifacts are safer to reuse.

Cache correctness is an optimization; it must not affect product truth.

---

# 91. Runtime Data Ownership

The user owns Project source.

Kallula owns/operates disposable runtime infrastructure.

For export:

Included:

- Project source;
- appropriate Project-owned configuration;
- Git history when requested.

Excluded by default:

- Kallula runtime container IDs;
- Preview access grants;
- internal network IDs;
- Run Engine Runtime;
- platform logs;
- Kallula secret metadata;
- Preview ephemeral database state.

---

# 92. Runtime Cost/Resource Accounting

The runtime should expose measurements sufficient for future budget enforcement:

- worker wall time;
- CPU/memory allocation/use where available;
- Preview uptime;
- supporting-service uptime;
- storage usage;
- image/build data where practical.

Exact billing is out of scope.

Resource facts should attach to Run/Attempt/Preview identity.

---

# 93. Runtime Security Escalation

If the Runtime Manager detects a policy violation or compromised workload signal, it may terminate the workload.

Examples:

- forbidden mount configuration;
- runtime isolation failure;
- control-network reachability breach;
- host/runtime error that invalidates isolation assumptions.

Such termination is a security/runtime failure, not safe stop or successful completion.

---

# 94. Runtime Manager Privilege

The Runtime Manager is privileged relative to workloads because it can create containers/networks/mounts.

Therefore:

- browser cannot call it directly;
- worker cannot call it directly;
- Preview cannot call it directly;
- inputs are validated normalized specs from trusted control-plane code;
- its own logs do not contain secret values;
- its API/socket, if separate, is on a private trust boundary.

No workload receives the container-runtime administrative socket.

---

# 95. Runtime Upgrade Strategy

Changing runtime implementation follows compatibility discipline.

Examples:

- new worker base image;
- new rootless OCI runtime version;
- new Preview gateway;
- new network driver.

Before becoming default:

- test worker start/resume;
- test workspace isolation;
- test child-env isolation;
- test resource limits;
- test network blocks;
- test Preview build/runtime;
- test secret injection separation;
- test cleanup/reconciliation.

Existing Runs remain pinned where runtime identity affects reproducibility/resume.

---

# 96. Implementation Sequence Implications

A practical implementation order inside this design is:

1. durable Workspace Manager;
2. local OCI Runtime Manager driver;
3. Worker container spec + resource/mount hardening;
4. Run Engine Runtime attachment;
5. Attempt lifecycle + reconciliation;
6. environment snapshot/runtime pack resolution;
7. stable source snapshot creation;
8. single-service Preview build/runtime;
9. Preview Gateway + separate origin access;
10. runtime logs/health;
11. runtime-only secret injection;
12. supporting services/multi-service plans;
13. backup/quotas/operational hardening.

This is sequencing guidance, not permission to implement before the remaining API/Test planning documents are ready.

---

# 97. Acceptance Criteria

## AC-ENV-001 — Disposable worker

Deleting an Execution Worker after a normal Attempt does not delete Project source, Git history, engine checkpoint state in the workspace, or Run Engine Runtime.

## AC-ENV-002 — Same workspace on resume

A resumed Run starts a new Execution Attempt attached to the same canonical Project workspace.

## AC-ENV-003 — Same Run Engine Runtime on resume

A resumed Attempt receives the same Run-scoped mutable engine runtime required for that Run's compatibility.

## AC-ENV-004 — Immutable engine installation

Worker execution cannot mutate the pinned Engine Installation.

## AC-ENV-005 — Single writer

Kallula refuses to start a second writable autonomous worker for a Project while another execution lease is valid or ownership remains unreconciled.

## AC-ENV-006 — Narrow workspace mount

A worker for Project A cannot read Project B's canonical workspace through normal mounts.

## AC-ENV-007 — No runtime socket

Worker and Preview containers do not receive Docker/Podman/container-runtime administrative sockets.

## AC-ENV-008 — Non-privileged workload

Hosted workloads are not launched privileged and do not use host network/PID namespaces.

## AC-ENV-009 — Finite resources

Workers, Preview application services, and supporting services have finite configured resource bounds.

## AC-ENV-010 — Worker environment pinning

An existing Run resumes with its pinned Environment Snapshot or fails compatibility; it does not silently resolve a different environment.

## AC-ENV-011 — Waiting releases compute

A Run in `WAITING_FOR_HUMAN` does not need its original worker container to remain alive.

## AC-ENV-012 — Safe stop is cooperative

A normal safe-stop request does not hard-kill the worker before engine-supported safe-boundary handling.

## AC-ENV-013 — Runtime-only Project secret

A credential assigned to Preview service `api` can be injected into that service without appearing in the coding-agent/Siesta environment.

## AC-ENV-014 — Build has no runtime secrets by default

Preview dependency/build commands do not receive assigned Project runtime credentials unless a separately approved future policy explicitly requires it.

## AC-ENV-015 — Stable Preview source

A Preview records and runs from an immutable source identity; files changing in the canonical workspace do not mutate the running Preview's source.

## AC-ENV-016 — Dirty workspace clarity

If workspace has uncommitted changes, initial Preview excludes them and identifies the exact committed source it is running.

## AC-ENV-017 — Preview/worker concurrency safety

Preview may run while a worker writes because Preview uses its own immutable source snapshot and has no write mount of the canonical workspace.

## AC-ENV-018 — Separate Preview network

Preview services cannot reach Kallula privileged control endpoints or other Project private networks through normal routing.

## AC-ENV-019 — No raw public ports

Generated application containers are not directly exposed on arbitrary public host ports; public access traverses the Preview Gateway.

## AC-ENV-020 — Preview cookie separation

Preview requests do not carry Kallula control-plane session cookies.

## AC-ENV-021 — Scoped Preview access

A Preview access grant cannot authorize normal Kallula control-plane API operations.

## AC-ENV-022 — Service-scoped credentials

A secret assigned only to backend service `api` is absent from frontend service `web`.

## AC-ENV-023 — Secret-free Runtime Plan

Persisted Runtime Plan contains credential identities/aliases but no plaintext secret values.

## AC-ENV-024 — Preview health distinct from verification

Making Preview `AVAILABLE` does not create/update a Verified State.

## AC-ENV-025 — Supporting services private

A supporting database/cache is not publicly routable unless explicitly supported by a future public-service policy.

## AC-ENV-026 — No arbitrary privileged Compose

A repository cannot gain host mounts, privileged mode, or runtime-socket access merely by containing Docker Compose configuration.

## AC-ENV-027 — Host restart reconciliation

After a supported host restart, Kallula preserves workspace/Run Engine Runtime and reconciles active Run/Preview records against actual runtime state.

## AC-ENV-028 — Orphan safety

Runtime cleanup does not delete a container/volume merely because it is unknown to in-memory state; durable identity/reconciliation is checked first.

## AC-ENV-029 — Log bounds

A service emitting unbounded output cannot consume unlimited persistent log storage; truncation/rate limiting is observable.

## AC-ENV-030 — Preview build timeout

A stuck Preview build terminates at a configured bound and leaves a failed Preview with logs instead of an indefinitely running hidden workload.

## AC-ENV-031 — Worker timeout classification

A worker killed for timeout/OOM/policy is not reported as successful completion.

## AC-ENV-032 — Workspace backup consistency

The documented backup process does not claim consistency while blindly copying an actively mutating workspace without a quiescence/snapshot mechanism.

## AC-ENV-033 — Runtime image identity

Environment Snapshot records immutable runtime image identity sufficient to know what an Attempt used.

## AC-ENV-034 — Preview source attribution

Runtime logs and Preview details can identify the exact source commit/Runtime Plan that produced the running application.

## AC-ENV-035 — Runtime configuration policy validation

Server-side launch validation rejects forbidden mounts, privileged mode, host networking, unauthorized secrets, and unavailable image identities even if a malformed client requests them.

## AC-ENV-036 — Preview update is explicit

A newer Project commit does not silently replace the source under an existing Preview; Preview stays pinned until update/restart.

## AC-ENV-037 — Application state disposable by default

Destroying a Preview may delete its development database/runtime volume without altering Project source or Verified State.

## AC-ENV-038 — Local dev insecurity explicit

Direct-process/local relaxed runtime mode cannot be mistaken for production-safe hosted execution.

## AC-ENV-039 — Multi-service private routing

Services in one Preview group can use isolated internal service discovery without exposing every service publicly.

## AC-ENV-040 — Runtime manager not workload-accessible

Execution Worker and Preview workloads cannot invoke the privileged Runtime Manager/container runtime administrative interface.

---

# 98. PRD Traceability

| PRD area | Runtime resolution |
|---|---|
| Workspace durability | §§8–10 |
| Run/Execution lifecycle | §§17–23 |
| Preview | §§31–54 |
| Environment | §§13–16, 62–64 |
| Runtime logs | §§51–52, 72–73 |
| Safe stop/resume | §§21–23 |
| Credentials | §§34, 45–46, 89 |
| Security | §§16, 27–30, 43–45, 71, 75, 93–94 |
| Portability | §§5–7, 80–81 |
| Reliability/recovery | §§56–61 |
| Resource budgets | §§26, 60, 92 |
| Existing repo import | §§85–86 |
| Clean export/source ownership | §§53, 91 |

---

# 99. Architecture Traceability

| Architecture area | Runtime resolution |
|---|---|
| §7.7 Execution Worker | §§4–6, 15–23 |
| §7.8 Workspace Manager | §§8–10, 61 |
| §7.12 Preview Controller | §§31–54 |
| §20 Execution lease | §§17, 19, 56, 82 |
| §24 Workspace/Git | §§8–10, 35–36 |
| §26 Preview state model | §§37–40 |
| §32 Infrastructure failure | §§55–57 |
| §33 Reconciliation | §§56–59 |
| §42 Trust boundaries | §§16, 27–30, 43–46, 71, 94 |
| §43 Initial deployment | §§5–7, 79–81 |
| Invariant A workspace uniqueness | §§9–10 |
| Invariant worker disposability | §§17–23 |
| Invariant secret isolation | §§34, 45–46 |

---

# 100. Siesta Adaptation Traceability

| Adaptation area | Runtime resolution |
|---|---|
| external workspace injection | §§9–10 |
| Run Engine Runtime | §§11–12 |
| durable Phase 0 suspension | §21 |
| safe stop/resume | §§22–23 |
| child environment | §§15–16, 18 |
| provider/network needs | §§27–29 |
| engine installation pinning | §§12, 62–63 |
| mutable Run learning assets | §11 |
| engine events/outcomes | §§17–20, 52 |
| compatibility suite | §§76, 95 |

---

# 101. Security Traceability

| Security area | Runtime implementation |
|---|---|
| worker secret boundary | §§15–16, 45 |
| Pi environment isolation | §§18, 25 |
| Project runtime credentials | §§34, 45–46, 89 |
| Preview isolation | §§27–30, 42–45, 71 |
| filesystem security | §§9–10, 36, 85–86 |
| GitHub separation | no GitHub authority added to worker/runtime |
| redaction | §§51–52, 72–73 |
| network protection | §§27–30 |
| runtime policy | §§75, 93–94 |
| backup | §61 |

---

# 102. UX Traceability

| UX area | Runtime source of truth |
|---|---|
| Environment page | §§13–16 |
| Run state/attempt | §§17–23 |
| Preview states | §§37–41 |
| Preview source label | §§35–36, 41 |
| Runtime logs | §§51–52 |
| health/failure | §§47, 49–50, 55 |
| credential runtime behavior | §§45–46 |
| compatibility warnings | §§62–63, 76–77 |
| stale Preview/update | §§41, 83 |
| Engine/System diagnostics | §§58, 63, 76, 95 |

---

# 103. Deliberately Open Implementation Decisions

This specification fixes the physical model while keeping replaceable technology choices open.

Still open for implementation/deployment selection:

1. exact OCI runtime product/driver;
2. exact rootless/user-namespace configuration;
3. exact worker base images/runtime packs initially shipped;
4. exact filesystem paths/storage backend;
5. exact cache implementation;
6. exact firewall/network-policy mechanism;
7. exact Preview gateway/proxy product;
8. exact separate Preview production domain;
9. exact Preview access-grant token/cookie format;
10. exact Runtime Plan auto-detection algorithms;
11. exact log transport/storage technology;
12. exact resource-limit numeric defaults;
13. exact workspace/Run Engine Runtime backup product;
14. exact runtime image build/promotion pipeline;
15. exact service health-check defaults;
16. exact retention durations;
17. exact metrics backend;
18. exact internal Runtime Manager programming interface.

These are implementation choices, not unresolved product semantics.

---

# 104. Implementation Status

The implementation plan now exists:

> [`Kallula — Implementation Plan.md`](./Kallula%20%E2%80%94%20Implementation%20Plan.md)

Use that document to sequence development and select the first-release implementation choices.

No more architecture document is required before coding starts.

The **Test & Compatibility Strategy** is still required before release. It is intentionally deferred until the implementation has real testable seams, runtime behavior, and compatibility fixtures.


# Appendix A — Runtime Filesystem Model

Conceptual hosted storage layout:

```text
kallula-data/
├── projects/
│   └── <project-id>/
│       ├── workspace/                 # canonical durable Project workspace
│       └── runs/
│           └── <run-id>/
│               └── engine-runtime/    # durable Run-scoped mutable engine state
│
├── runtime-cache/                     # disposable
│
└── preview-temp/                      # disposable/rebuildable
    └── <preview-id>/
        ├── source/                    # immutable snapshot
        ├── build/                     # disposable output
        └── volumes/                   # disposable Preview service data
```

The exact path is not part of the public contract.

Credential storage and root keys are intentionally absent from this workspace tree.

---

# Appendix B — Worker Mount Matrix

| Mount | Worker access | Durable | Exported as source |
|---|---|---:|---:|
| Engine Installation | read-only | Yes/versioned | No |
| Canonical Workspace | read-write | Yes | Yes, clean export rules |
| Run Engine Runtime | read-write | Yes for Run | No |
| Scratch/tmp | read-write | No | No |
| Package cache | read-write | Optional cache | No |
| Host projects root | No | — | — |
| Credential store | No | — | — |
| Runtime socket | No | — | — |
| Control-plane source/config | No | — | — |

---

# Appendix C — Preview Runtime Matrix

| Resource | Build phase | App runtime | Supporting service |
|---|---:|---:|---:|
| Immutable Preview source | read-only/copy | read-only/prepared | No |
| Build scratch | read-write | No | No |
| Runtime writable scratch | No | read-write | read-write |
| Project runtime secrets | No by default | Explicit per service | Only if explicitly defined |
| Public package internet | Policy-dependent | Usually not needed for build-complete app | Usually no |
| Preview project network | Limited | Yes | Yes |
| Control network | No | No | No |
| Public ingress | No | Only declared service via gateway | No |
| Runtime socket | No | No | No |

---

# Appendix D — Preview Source/Trust Examples

## Current committed but unverified source

```text
Project workspace
HEAD = abc123
dirty = false

Preview:
source = abc123
label = Current source · not verified
```

## Dirty active workspace

```text
Project workspace
HEAD = abc123
dirty = true

Preview:
source = abc123
label = Latest committed source
notice = Current workspace has newer uncommitted changes
```

## Verified source

```text
Verified State = def456

Preview:
source = def456
label = Verified source
```

The Preview health badge remains separate from the source trust label.

---

# Appendix E — Runtime Decision Summary

| Topic | Decision |
|---|---|
| Hosted isolation | OCI-compatible container runtime or stronger |
| Reference mode | rootless/user-namespace-isolated where practical |
| Host process mode | development only |
| Worker lifetime | one disposable runtime per Execution Attempt |
| Workspace | stable durable Project mount |
| Run engine mutable state | separate durable Run Engine Runtime |
| Engine installation | immutable/read-only |
| Environment | immutable Environment Snapshot per Run |
| Runtime packs | curated/prebuilt initially |
| Project OS package install | no arbitrary host mutation |
| Coding worker secrets | no Project runtime secrets by default |
| Preview build secrets | no Project runtime secrets by default |
| Application secrets | service-scoped runtime injection |
| Preview source | immutable committed source snapshot initially |
| Preview runtime | separate from coding worker |
| Preview networking | isolated Project/Preview network |
| Public access | Preview Gateway only |
| Preview origin | separate production site/domain boundary |
| Raw public ports | not exposed |
| Supporting services | curated/private by default |
| Compose/Dockerfile authority | not privileged runtime authority in initial product |
| Worker/Preview runtime socket | never mounted |
| Crash recovery | reconcile durable state + runtime inventory |
| Multi-host | future driver/storage evolution, not required initially |

---

# Final Runtime Rule

> **Kallula treats compute as replaceable and state as intentional: source and resumable engine state persist outside disposable workers; generated applications run in a separate constrained Preview domain; and no container, service, network, mount, or secret crosses those boundaries without an explicit product-level reason.**
