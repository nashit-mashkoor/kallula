# Kallula — Security & Credentials Design

**Document status:** Normative security and credentials design — implementation started
**Product:** Kallula
**Primary product specification:** [`Kallula — Product Requirements Document.md`](./Kallula%20%E2%80%94%20Product%20Requirements%20Document.md)
**Parent architecture:** [`Kallula — System Architecture & State Model.md`](./Kallula%20%E2%80%94%20System%20Architecture%20%26%20State%20Model.md)
**Engine adaptation specification:** [`Kallula — Siesta Engine Adaptation Specification.md`](./Kallula%20%E2%80%94%20Siesta%20Engine%20Adaptation%20Specification.md)
**UX & interaction specification:** [`Kallula — UX & Interaction Specification.md`](./Kallula%20%E2%80%94%20UX%20%26%20Interaction%20Specification.md)
**Execution environment & Preview design:** [`Kallula — Execution Environment & Preview Design.md`](./Kallula%20%E2%80%94%20Execution%20Environment%20%26%20Preview%20Design.md)
**API & data contract specification:** [`Kallula — API & Data Contract Specification.md`](./Kallula%20%E2%80%94%20API%20%26%20Data%20Contract%20Specification.md)
**Implementation plan:** [`Kallula — Implementation Plan.md`](./Kallula%20%E2%80%94%20Implementation%20Plan.md)  
**Implementation status:** Tracked by the [Implementation Plan](./Kallula%20%E2%80%94%20Implementation%20Plan.md)
**Purpose:** Define Kallula's security model, trust boundaries, authentication/session requirements, credential domains, encryption and key hierarchy, secret lifecycle, worker/provider/GitHub exposure rules, preview isolation requirements, redaction, auditability, compromise response, and security acceptance criteria before execution-environment and API implementation choices are frozen.
**Audience:** Security, backend/control-plane, runner, engine-integration, infrastructure, frontend, GitHub/integration, QA, and future operators.

> **Normative relationship:** The PRD defines required product security behavior and invariants. The **System Architecture & State Model** defines ownership and trust boundaries. The **Siesta Engine Adaptation Specification** defines the engine-facing places where credentials and environments can cross into Siesta/Pi. The **UX & Interaction Specification** defines how security-sensitive states and operations appear to users. The **Execution Environment & Preview Design** defines the concrete workload separation, mount/network model, runtime-only service-scoped secret injection, Preview gateway/origin/access flow, and cleanup/reconciliation mechanisms that implement this policy. The **API & Data Contract Specification** defines how security-sensitive resource metadata, write-only secret inputs, never-returned fields, object authorization, ETags, idempotent sensitive commands, Preview access operations, and Audit Events cross the application boundary. This document remains authoritative for security policy and credential-flow semantics.

> **Security posture:** Kallula treats autonomous agents, imported repositories, generated source, generated applications, model output, and Preview workloads as **untrusted or potentially adversarial content** even when Kallula itself produced them. Trusted control-plane capabilities and long-lived secrets must not be inherited merely because an autonomous process needs to build or run a Project.

> **Secret-handling rule:** Prefer **non-exposure** over redaction. A secret that an autonomous agent or Preview does not need must never enter that process in the first place. Redaction is defense in depth, not permission to over-share secrets.

---

# 1. Purpose

Kallula executes autonomous coding agents against user-controlled source code and can run the applications those agents generate.

That combination creates security boundaries that are materially different from a normal CRUD application:

- repository content can contain instructions intended to manipulate an agent;
- generated code can execute arbitrary logic;
- package installation can execute third-party code;
- the coding agent has file and shell capabilities;
- model providers may require authentication;
- GitHub operations require authority over repositories;
- Project applications may need runtime secrets;
- engine/runtime logs can accidentally contain sensitive values;
- generated Preview applications are reachable from a browser;
- a worker crash must not cause Kallula to “recover” by broadening permissions;
- a future multi-user deployment must not require redesigning every credential identity.

This specification resolves the security policy before implementation chooses exact infrastructure products.

It answers:

- What does Kallula trust?
- What does it explicitly not trust?
- Which secret classes exist?
- Which component is allowed to decrypt each class?
- What may enter an Execution Worker?
- What may enter the Siesta/Pi process?
- What may enter generated application runtime processes?
- How are credentials encrypted at rest?
- Where does the root encryption material live?
- What is stored in the database and backups?
- How are credentials created, replaced, assigned, revoked, and deleted?
- How does GitHub access work without handing broad tokens to agents?
- How are model-provider credentials handled?
- How does Preview remain separated from Kallula's authenticated control plane?
- When and how does redaction happen?
- What security-relevant actions are audited?
- What happens when compromise or credential leakage is suspected?

---

# 2. Scope

This specification covers:

- browser authentication and session security requirements;
- authorization principles;
- CSRF/origin requirements;
- credential taxonomy;
- secret metadata and lifecycle;
- encryption at rest;
- key hierarchy and rotation;
- control-plane secret access;
- Project credential assignment;
- engine/model-provider credentials;
- worker and Pi environment construction;
- runtime secret injection policy;
- GitHub integration authentication;
- Preview/control-plane origin separation;
- worker/Preview network security constraints;
- logging and redaction;
- source/artifact secret handling;
- audit records;
- backup/restore security;
- compromise response;
- security validation and acceptance criteria.

This document intentionally does **not** choose:

- a specific cloud KMS;
- a specific Vault product;
- a specific authentication vendor;
- a container runtime;
- Kubernetes;
- a firewall implementation;
- a service mesh;
- exact database table layouts;
- exact API routes;
- exact OS sandbox technology;
- exact Preview router/proxy technology.

Those are implementation choices constrained by this policy.

---

# 3. Security Goals

Kallula must preserve the following outcomes.

## 3.1 Control-plane authority stays out of autonomous workloads

A compromised agent, Project dependency, generated application, or Preview must not automatically gain:

- Kallula database credentials;
- credential-decryption authority;
- root encryption keys;
- GitHub App private keys;
- broad GitHub tokens;
- cloud infrastructure credentials;
- host SSH keys;
- Docker daemon/socket authority;
- credentials belonging to another Project.

## 3.2 Secret exposure is explicit and minimal

A credential may cross a trust boundary only when:

1. the receiving component has a documented need;
2. the credential domain permits that type of exposure;
3. the Project/Run policy permits it;
4. the exposure is scoped to the smallest practical lifetime and target;
5. the operation is auditable.

## 3.3 Stored secret values are not readable product data

Normal product APIs and UI flows treat stored secrets as:

- create;
- replace;
- assign;
- unassign;
- revoke;
- delete;

not:

- list plaintext;
- retrieve plaintext;
- reveal.

## 3.4 Generated code is portable without exporting Kallula secrets

Downloading or publishing a Project must not be the mechanism by which Kallula's platform or integration credentials leave the platform.

## 3.5 Security failures fail closed

If Kallula cannot establish:

- ownership;
- secret authorization;
- encryption-key availability;
- engine-provider authorization;
- Preview isolation;
- GitHub permission;
- safe redaction behavior for a sensitive channel;

the security-sensitive operation fails rather than silently broadening access.

---

# 4. Explicit Non-Goals and Threat Assumptions

## 4.1 Initial user model

The initial product may primarily serve one authenticated owner.

This simplifies authorization UX, but **does not** justify:

- omitting ownership fields;
- using guessable resource identifiers as authorization;
- sharing credentials globally without scope;
- cross-Project secret inheritance.

All protected resources retain an owning principal or ownership scope.

## 4.2 Host-root compromise

The first release does not claim to protect secrets from an attacker who has obtained full root/administrator control over the Kallula host while decrypted material is in use.

The system should still:

- encrypt persistent credential storage;
- minimize plaintext lifetime;
- keep root key material separate from the database;
- make later migration to an external KMS/secret service possible.

## 4.3 Malicious user with legitimate ownership

Kallula is not required to prevent the Project owner from downloading their own source or intentionally entering their own secrets into their own source code.

It must prevent the platform from accidentally leaking unrelated or platform-owned secrets.

## 4.4 Model-provider confidentiality

Kallula cannot guarantee confidentiality once authorized content has been transmitted to an external model provider.

Therefore the product must minimize transmitted data and clearly separate provider authorization from Project secrets.

---

# 5. Threat Model

The design assumes the following adversarial or failure conditions are plausible.

## 5.1 External attacker

May attempt:

- session theft;
- credential stuffing;
- CSRF;
- API authorization bypass;
- path traversal;
- injection;
- Preview abuse;
- GitHub integration misuse.

## 5.2 Malicious or compromised repository

Imported source may contain:

- prompt-injection text;
- malicious build scripts;
- dependency hooks;
- symlinks;
- intentionally sensitive-looking data;
- code that attempts to reach internal services.

## 5.3 Malicious or compromised autonomous agent

The model/agent may:

- execute unexpected shell commands;
- attempt to inspect environment variables;
- read accessible files;
- copy data into source/logs;
- attempt network exfiltration;
- follow malicious repository instructions.

Kallula therefore cannot use “the model would not do that” as a security control.

## 5.4 Generated Preview workload

Generated application code may:

- attempt to read local files;
- attempt SSRF/internal network access;
- expose injected secrets;
- set browser cookies;
- serve malicious JavaScript;
- attempt interaction with Kallula's authenticated browser context.

## 5.5 Compromised integration/provider

External providers may be unavailable, misconfigured, or compromised.

Kallula must scope their authority and avoid using one provider credential as general platform authority.

## 5.6 Operational mistakes

Operators may:

- back up ciphertext without the required key material;
- accidentally log environment variables;
- rotate a key incorrectly;
- misconfigure Preview routing;
- mount the wrong Project workspace.

Security design must make such failures detectable and preferably fail closed.

---

# 6. Trust Domains

```text
                 TRUSTED
+--------------------------------------+
| Kallula Control Plane                |
|                                      |
|  +-------------------------------+   |
|  | Credential / Crypto Boundary  |   |
|  +-------------------------------+   |
|                 |                    |
|  +--------------+----------------+   |
|  | Runtime / Integration control |   |
|  +--------------+----------------+   |
+-----------------+--------------------+
                  |
        explicit narrow grants
                  |
        +---------+----------+
        |                    |
        v                    v
+---------------+    +---------------+
| Coding Worker |    | Preview App   |
|   UNTRUSTED   |    |   UNTRUSTED   |
+---------------+    +---------------+

No workload inherits control-plane secrets.
```


Kallula uses the following security domains.

```text
Browser
  │
  ▼
Kallula Web / Control Plane
  │
  ├── Control DB
  ├── Credential Service / Crypto Boundary
  ├── Trusted Integration Executor
  └── Runner / Execution Coordinator
          │
          ▼
      Execution Worker
          │
          ├── Kallula Adapter
          │     ▼
          │   Siesta
          │     ▼
          │     Pi / model invocation
          │
          └── Generated application runtime
                 ▼
              Preview route
```

External systems include:

- GitHub;
- model providers;
- future deployment providers;
- user-configured Project services.

The important rule is that proximity in one process or host does not imply equal authority.

---

# 7. Trust Classification

| Component/content | Trust classification | Notes |
|---|---|---|
| Control Plane | trusted | owns product state and authorization |
| Credential Service / crypto boundary | highly trusted | may decrypt authorized secrets |
| Control DB | trusted storage, not key authority | may contain ciphertext and metadata |
| Runner/Coordinator | trusted orchestration | must not need broad secret read access |
| Integration Executor | trusted, narrowly privileged | GitHub/provider-specific trusted actions |
| Kallula Adapter | trusted bridge | more privileged than engine; constrained |
| Siesta orchestration | semi-trusted execution component | must not receive control-plane authority |
| Pi/coding agent | untrusted autonomous workload for secret purposes | file/shell capable |
| Imported source | untrusted content | may include prompt/build attacks |
| Generated source | untrusted content | generated does not mean safe |
| Generated runtime | untrusted workload | separate from control plane |
| Preview browser content | untrusted web origin | must not inherit control-plane cookies |
| Model provider | external trust domain | receives only intentionally transmitted context |
| GitHub | external trusted integration | authority via scoped app installation |

---

# 8. Security Invariants

### Invariant S1 — No authority by inheritance

A child process does not receive secrets merely because its parent process has them.

### Invariant S2 — No control-plane secret in Project source

Kallula platform, database, GitHub App, encryption-root, and cloud-control credentials must never be written into canonical Project source by normal system behavior.

### Invariant S3 — No routine plaintext retrieval

Credential values are never returned by normal read/list APIs after creation.

### Invariant S4 — Secret metadata is separate from secret value

UI and normal product logic can operate on credential identity/status without decryption.

### Invariant S5 — Preview is not control plane

Generated web applications never share Kallula's trusted browser origin/session authority.

### Invariant S6 — Agents do not publish to GitHub

GitHub publishing authority belongs to a trusted integration path, not the coding agent.

### Invariant S7 — Project credentials are opt-in

Project runtime credentials are not automatically injected into worker/agent processes.

### Invariant S8 — Provider credentials are not general-purpose Project secrets

Model-provider authentication is scoped to model invocation and cannot imply control-plane or GitHub authority.

### Invariant S9 — Key material is separated

The key-encryption/root key is not stored as ordinary ciphertext next to the encrypted credential database.

### Invariant S10 — Redaction does not authorize exposure

A channel is not considered safe merely because output will later be redacted.

### Invariant S11 — Audit records never contain secret values

Security auditability must not become another secret leak.

### Invariant S12 — Security state is fail closed

Unknown ownership, unknown policy, unavailable decryption key, or incompatible security configuration denies the sensitive action.

---

# 9. Identity and Authentication

## 9.1 Authentication abstraction

Kallula may support different authentication providers over time.

The product security contract is provider-independent.

The authenticated subject must resolve to a stable internal principal ID.

Provider email/username is display metadata, not the canonical authorization identity.

## 9.2 Browser session model

The browser uses a **server-managed authenticated session**.

The initial web product must not require long-lived bearer credentials stored in browser local storage.

Session requirements:

- cryptographically strong unpredictable session identifier;
- session state validated server-side;
- Secure cookie in production;
- HttpOnly cookie;
- host-only cookie where practical;
- SameSite protection appropriate to the configured auth flow;
- session rotation after successful authentication and privilege-sensitive transitions;
- expiration and revocation;
- logout invalidates the server session.

**KSC-REQ-001** — Long-lived authentication tokens must not be stored in browser `localStorage`.

**KSC-REQ-002** — Control-plane authentication cookies must not use a broad parent-domain `Domain` attribute that would make them available to Preview hosts.

## 9.3 Authentication transport

Production authentication and authenticated application traffic require HTTPS.

Plain HTTP is acceptable only for explicitly configured local development environments that cannot be reached as a hosted production surface.

## 9.4 CSRF

If authentication uses cookies, state-changing browser requests must use CSRF defenses appropriate to the transport, including:

- SameSite cookie policy;
- unpredictable anti-CSRF token or equivalent framework protection where required;
- origin/referer validation for security-sensitive actions;
- no state-changing GET endpoints.

WebSocket connections, if later used, must validate authenticated subject and browser origin.

## 9.5 Session storage

External identity-provider access/refresh tokens, if used, should remain server-side when possible.

The browser receives Kallula session authority, not reusable third-party integration authority.

---

# 10. Authorization

## 10.1 Object authorization

Every protected operation must authorize the authenticated principal against the referenced object.

This applies to:

- Project;
- Run;
- Execution Attempt;
- Pending Interaction;
- Artifact;
- Credential;
- Agent Profile;
- Integration;
- Engine diagnostics where restricted.

Stable UUID-like identifiers are not an authorization mechanism.

## 10.2 Ownership representation

Initial ownership may be one owner per object.

The schema/API must still represent an owner/principal explicitly so future team RBAC does not need re-identifying every resource.

## 10.3 Server-side enforcement

Frontend hiding is not authorization.

All security-sensitive action validation occurs server-side.

## 10.4 Command authorization

Durable commands such as:

- answer interaction;
- stop;
- resume;
- assign credential;
- rotate/delete credential;
- connect/disconnect GitHub;
- publish;

must bind actor identity to the durable command/audit record.

---

# 11. Credential Taxonomy

Kallula distinguishes credential domains because each has different exposure rules.

## 11.1 Root/bootstrap key material

Purpose:

- protect or unwrap credential encryption keys.

Examples:

- Kallula root/master encryption key;
- external KMS authentication/bootstrap material.

Allowed domain:

- credential/crypto boundary only.

Forbidden:

- browser;
- Project workspace;
- Execution Worker;
- Siesta;
- Pi;
- generated runtime;
- Preview;
- logs;
- database plaintext.

## 11.2 Control-plane service credentials

Examples:

- control database password;
- internal object/storage credentials;
- infrastructure control credentials.

Allowed:

- only the service that requires them.

Forbidden by default:

- Runner child processes;
- Execution Worker;
- agent;
- Project application.

## 11.3 Integration credentials

Examples:

- GitHub App private key/client secret;
- future deployment-provider credentials.

Allowed:

- trusted integration service/path only.

Agents do not receive them.

## 11.4 Engine/provider credentials

Examples:

- model-provider API tokens;
- credentials required to reach an inference gateway.

Allowed:

- narrow model-invocation path defined by the configured provider integration.

They are not Project runtime credentials.

## 11.5 Project runtime credentials

User-provided secrets used by the application being built.

Examples:

- `OPENAI_API_KEY`;
- `SUPABASE_KEY`;
- `STRIPE_SECRET_KEY`;
- application database credentials.

Allowed:

- only Project runtime processes explicitly assigned the credential;
- future trusted test command execution if a later approved feature permits it.

Forbidden by default:

- coding agent;
- general worker shell;
- Siesta prompt;
- source tree.

## 11.6 Ephemeral grants

An ephemeral grant is temporary authority derived from a stored credential without exposing the long-lived source credential broadly.

Examples:

- short-lived GitHub installation token;
- temporary runtime environment materialization;
- future provider session token.

Ephemeral grants should be preferred when the external service supports them.

---

# 12. Credential Resource Model

Each Credential has non-secret metadata including at least:

- stable internal ID;
- owner/principal scope;
- user-visible name;
- credential domain/type;
- provider/category;
- creation time;
- last replacement time;
- status;
- assignment metadata;
- encryption key/version metadata;
- optional validation status;
- audit references.

The secret value is stored separately as protected ciphertext.

## 12.1 Credential names

Names are identifiers for humans/configuration, not the secret itself.

A Project may record:

```text
OPENAI_API_KEY
```

without storing or displaying its value.

## 12.2 Versions

Replacing a secret creates a new credential-value version under the same logical Credential identity.

Audit records can refer to an opaque value-version identifier.

Historical Runs record the Credential identity/name/policy used, not plaintext.

## 12.3 Secret hashes

Do not use an unsalted plain hash of a secret as a publicly visible fingerprint.

If a value-comparison fingerprint is needed internally for redaction/deduplication, it must use a keyed construction or remain inside the trusted secret boundary.

---

# 13. Encryption Architecture

## 13.1 Envelope encryption

Credential values use envelope encryption.

Conceptually:

```text
plaintext secret
    ↓
random per-value Data Encryption Key (DEK)
    ↓
authenticated encryption
    ↓
ciphertext + nonce/tag

DEK
    ↓
wrapped/encrypted by active Key Encryption Key (KEK)
    ↓
wrapped DEK + key identifier
```

The persistent credential record may store:

- ciphertext;
- nonce/IV;
- authentication tag where not bundled;
- wrapped DEK;
- KEK identifier/version;
- algorithm/version marker;
- credential/value version metadata.

It must not store the plaintext KEK.

## 13.2 Authenticated encryption

Secret encryption must use a modern authenticated-encryption primitive.

The exact library/provider is an implementation choice, but acceptable designs include well-supported AEAD constructions such as:

- AES-256-GCM;
- XChaCha20-Poly1305.

Custom cryptography is prohibited.

## 13.3 Associated data

Encryption should bind stable non-secret context as authenticated associated data where practical, such as:

- Credential ID;
- owner scope;
- value version.

This prevents moving ciphertext between unrelated records without detection.

## 13.4 Root/KEK storage

The active KEK or authority capable of unwrapping DEKs must exist outside normal application database records.

Acceptable initial mechanisms include:

- deployment-mounted protected key material;
- OS/service secret facility;
- external KMS/secret manager.

The first implementation may be operationally simple but must present the same logical `KeyProvider`/crypto boundary so migration does not need changing Credential semantics.

**KSC-REQ-010** — The database alone must be insufficient to decrypt stored credential values.

## 13.5 Local-development mode

A development-only key may be loaded from a local ignored file or environment bootstrap mechanism.

Requirements:

- never committed;
- explicit development-mode warning;
- not accepted as production-safe configuration;
- test fixtures use fake secrets.

---

# 14. Key Lifecycle and Rotation

## 14.1 Key identity

Every encrypted credential value records which KEK version protects its DEK.

## 14.2 KEK rotation

Rotating the KEK should normally re-wrap DEKs rather than require plaintext secret re-entry.

The rotation procedure must:

1. introduce new active KEK;
2. decrypt/unwrap old DEK under old key;
3. wrap DEK under new key;
4. persist new key identity atomically;
5. verify decryptability;
6. retain old KEK only for the defined migration/recovery window;
7. retire old key after all required values are migrated and backups are understood.

## 14.3 Credential rotation

Credential value rotation is separate from KEK rotation.

User/provider credential rotation creates a new secret-value version.

## 14.4 Backup implications

Encrypted-data backups are only useful if required key material is backed up independently and securely.

The backup process must document:

- ciphertext backup;
- KEK/key-provider recovery path;
- key version inventory;
- restore validation.

Do not place the only copy of the root key inside the same backup archive as the database.

---

# 15. Plaintext Secret Lifetime

Plaintext should exist only:

- while receiving a create/replace request;
- inside the trusted crypto boundary during decrypt/use;
- inside the narrowly authorized target process environment or input mechanism for the permitted lifetime.

Plaintext must not intentionally appear in:

- application logs;
- audit logs;
- error payloads;
- database metadata;
- Run configuration snapshots;
- events;
- metrics labels;
- traces;
- Git commit messages;
- source downloads.

Memory zeroization cannot be guaranteed perfectly in a managed language runtime; therefore minimizing exposure and process boundaries remain primary controls.

---

# 16. Credential API Semantics

Exact routes are deferred, but semantics are fixed.

## 16.1 Create

Input:

- metadata;
- plaintext value.

Output:

- metadata/status only.

Never echo the plaintext.

## 16.2 Read/list

Returns metadata only.

There is no normal secret-value field.

## 16.3 Replace

Accepts a new plaintext value and creates/replaces the active value version.

Response is metadata only.

## 16.4 Assign/unassign

Changes which Project/runtime scope may request use of the Credential.

It does not copy the plaintext into Project state.

## 16.5 Delete

Deletion requires authorization and impact checks.

The product should:

- prevent future use;
- remove or schedule removal of ciphertext according to retention/recovery policy;
- keep non-secret audit history.

Deletion semantics for credentials currently in use must be explicit in the API/Data Contract Specification.

## 16.6 Caching

Secret create/replace responses must use no-store/no-cache semantics appropriate to the frontend/API stack.

Request bodies containing secrets must be excluded from request logging.

---

# 17. Credential Assignment Semantics

Assignment is authorization, not exposure.

Example:

```text
Project A
✓ OPENAI_API_KEY
✓ SUPABASE_KEY
☐ STRIPE_SECRET_KEY
```

means Project A may request those secrets in the permitted runtime contexts.

It does **not** mean:

- all Project processes inherit them;
- the coding agent may read them;
- they are written to `.env`;
- they are stored in Git.

**KSC-REQ-020** — Project credential assignment must be represented by credential IDs/aliases and policy, never copied plaintext.

---

# 18. Run Configuration and Secret Reproducibility

Run configuration snapshots record:

- credential identities/names permitted;
- credential domain/policy;
- relevant assignment state;
- provider/integration identity where needed.

They do not record:

- secret values;
- reversible secret material.

Historical reproducibility deliberately excludes secret-value reconstruction.

Security wins over bit-for-bit replay of secrets.

When a secret is rotated, historical Run metadata remains attributable without retaining plaintext.

---

# 19. Control-Plane Secret Access

## 19.1 Narrow decrypt authority

Only the credential/crypto boundary should have general decrypt capability.

Other components request narrowly authorized operations.

## 19.2 Runner

The Runner/Coordinator may determine **which named credential** a Run is allowed to use, but should not need to list/decrypt every secret globally.

## 19.3 Web process

Normal web handlers may accept secret creation/replacement, but plaintext should be passed directly into the credential boundary and discarded.

Read handlers never decrypt merely to render settings pages.

## 19.4 Database

Database compromise should expose:

- metadata;
- ciphertext;

but not the root KEK.

---

# 20. Execution Worker Secret Boundary

The Execution Worker is not a trusted home for control-plane secrets.

Its initial process environment must be constructed from an explicit allowlist.

It must not inherit the control-plane process environment wholesale.

## 20.1 Forbidden by default

The worker must not receive:

- Kallula database credentials;
- KEKs/root encryption key;
- GitHub App private key;
- broad GitHub OAuth/PAT credentials;
- cloud-control credentials;
- host SSH keys;
- unrelated Project credentials;
- secrets of another Project;
- Docker socket credentials.

## 20.2 Allowed categories

A worker may receive:

- non-secret runtime basics required to start;
- Run/Attempt correlation identifiers;
- canonical workspace path/mount information;
- immutable engine/runtime locations;
- adapter configuration;
- narrowly scoped engine-provider access where the provider design requires it.

## 20.3 Worker secret manifest

For each Execution Attempt, the trusted coordinator should derive a manifest of secret **identities/categories** made available to that Attempt.

The manifest contains no plaintext and is auditable.

---

# 21. Siesta/Pi Child Environment

The Siesta adapter's child environment must be constructed explicitly.

The current upstream behavior of copying `os.environ` wholesale is prohibited in hosted Kallula operation.

## 21.1 Minimum categories

The Pi/engine environment may include only documented needs such as:

- `PATH` and minimal process runtime values;
- locale where required;
- Python/module path required by Siesta;
- isolated Pi profile path;
- model endpoint/provider configuration;
- narrow provider authorization if unavoidable;
- explicit non-secret Run/Attempt identifiers.

## 21.2 Deny-by-default test

The compatibility/security suite must seed representative forbidden secrets into the parent environment and verify they are absent from:

- Siesta child;
- Pi child;
- agent shell command environment where applicable.

## 21.3 No hidden fallback inheritance

If required environment filtering breaks a provider/engine integration, that provider integration is considered incompatible until the required key is deliberately added to its security manifest.

Do not restore broad inheritance as a compatibility shortcut.

---

# 22. Model-Provider Credential Strategy

Model-provider authentication is a special case because the engine must invoke models while the agent itself is not trusted with broad secrets.

## 22.1 Preferred design

Prefer provider connectivity where the raw long-lived provider credential remains outside the coding-agent shell environment.

Examples conceptually include:

- local/provider gateway holding upstream authentication;
- brokered model invocation;
- short-lived scoped provider token where available.

## 22.2 If raw provider token exposure is unavoidable

The provider integration must explicitly declare:

- which subprocess receives it;
- whether agent tool commands can inherit/read it;
- token scope;
- lifetime;
- revocation method;
- accepted residual risk.

A broad platform credential must never be reused for this purpose.

## 22.3 Provider capability validation

An Engine Installation/provider combination is not production-compatible merely because inference works.

Compatibility testing must validate its declared secret exposure model.

**KSC-REQ-030** — Provider authentication requirements are part of Engine/Environment security compatibility metadata.

---

# 23. Project Runtime Secret Policy

## 23.1 Initial default

Autonomous coding agents do not receive plaintext Project runtime secrets.

Siesta can build software that expects configuration by name and can use:

- mocks;
- test doubles;
- local substitutes;
- non-secret fixtures.

## 23.2 Generated application runtime

A generated application may receive assigned Project runtime credentials when:

- the application runtime is started by a trusted Kallula runtime launcher;
- the credential is assigned to the Project;
- runtime use is explicitly permitted;
- injection occurs outside the source tree;
- logs are subject to redaction;
- the Preview/runtime network boundary is enforced.

## 23.3 Separation from agent shell

Runtime-secret injection must not make the same plaintext automatically available to the coding agent's general shell.

[`Kallula — Execution Environment & Preview Design.md`](./Kallula%20%E2%80%94%20Execution%20Environment%20%26%20Preview%20Design.md) preserves this separation by running generated applications outside the coding worker and injecting Project credentials only into declared application services.

## 23.4 Real-secret tests

A generic agent-accessible “run tests with all Project secrets” feature is **not** part of the initial design.

A future Secret Execution Broker may execute approved commands with named credentials without revealing values to the model. It requires a separate security review.

---

# 24. Secret Injection Mechanisms

Exact runtime technology is deferred, but acceptable mechanisms must preserve these semantics:

- inject only into the target process/service;
- no source-tree `.env` persistence by Kallula;
- no Git staging;
- no command-line arguments where secrets would be visible in process listings when a safer mechanism exists;
- no inclusion in generated launch scripts persisted to the workspace;
- cleanup/revocation after process termination where applicable.

Environment variables may be used for application compatibility, but only within the target runtime boundary, not as a blanket worker environment.

---

# 25. GitHub Authentication Model

## 25.1 Production model

The preferred initial hosted GitHub integration is a **GitHub App installation model**.

Reasons:

- repository-scoped installation;
- explicit permissions;
- short-lived installation access tokens;
- revocable installation;
- no need to hand a user's broad personal token to agents.

The exact App permission set must be the minimum required for enabled features.

## 25.2 Trusted integration path

GitHub authentication material belongs to a trusted Integration Executor.

Autonomous agents do not receive:

- GitHub App private key;
- installation tokens;
- broad user OAuth token;
- PAT.

## 25.3 Repository import

The trusted integration path may materialize an authorized repository into the canonical workspace.

If Git requires temporary credentials:

- they are supplied only to the trusted Git process;
- they are not stored in repository config;
- remote URLs do not embed credentials;
- credential-helper state is ephemeral and isolated.

After import, normal local Git operations can proceed without GitHub authority.

## 25.4 Publish/push/PR

Publishing is performed by the trusted Integration Executor or an equivalently constrained trusted Git operation.

The coding agent may prepare commits/branches locally, but it does not authorize remote push.

## 25.5 Token lifetime

Use short-lived installation tokens generated on demand.

Do not persist installation access tokens as long-lived credential records when they can be regenerated.

## 25.6 Local development fallback

A developer PAT may be supported only as an explicit local/development fallback.

It is not the default production credential model.

The UI and configuration must make that distinction clear.

**KSC-REQ-040** — No GitHub secret is required inside Siesta/Pi merely to perform local Git commits.

---

# 26. GitHub Permission Strategy

Permissions are capability-based.

For example, features may require separate permission groups for:

- repository metadata/read;
- contents read for import;
- contents write for push;
- pull-request creation/update.

Kallula should not request write permission for an installation that only imports repositories.

Permission changes must be explicit and auditable.

Exact current GitHub permission names/API details should be validated against GitHub documentation during implementation rather than hard-coded in this design.

---

# 27. Integration Credential Separation

GitHub and future integrations are Kallula platform integrations.

They must not be represented as ordinary Project runtime credentials.

Why:

- their trust domain differs;
- revocation differs;
- their authority can span repositories/projects;
- autonomous agents must not inherit them.

The UI distinction required by the UX specification reflects a real backend security boundary.

---

# 28. Preview Security Model

Generated application Preview is treated as an untrusted web application.

## 28.1 Origin separation

Preview must not share Kallula's trusted control-plane origin.

Control-plane session cookies must be host-only and must never be sent to Preview.

The preferred hosted design uses a Preview origin/site that cannot receive Kallula control-plane cookies even if Preview JavaScript is malicious.

A separate registrable domain is preferred over relying solely on subdomain separation.

## 28.2 Browser isolation

If Preview is embedded:

- it remains cross-origin;
- sandboxing should be applied consistent with required application behavior;
- Kallula must not grant unnecessary iframe capabilities;
- `postMessage` interactions, if any, require exact-origin validation and typed messages.

## 28.3 Preview authentication

Preview access may require Kallula-controlled authorization.

That authorization must not be implemented by giving the Preview application the user's Kallula session cookie.

Use a separate Preview access mechanism designed by the Execution Environment & Preview specification.

## 28.4 Network isolation

Preview runtime must not have unrestricted connectivity to:

- Kallula control-plane database;
- credential service;
- internal administration endpoints;
- host metadata/instance credential endpoints;
- other Project private runtimes.

Project-local supporting services may be reachable only within the Project runtime network/policy.

## 28.5 Secret exposure

Preview may receive only assigned Project runtime credentials needed by that application.

It must never receive:

- control-plane credentials;
- GitHub App credentials;
- KEKs;
- unrelated Project secrets.

---

# 29. Execution Worker Network Security Constraints

The later execution-environment design must provide enforceable network zones.

At minimum:

- worker/agent network path to approved model provider/gateway;
- Project dependency/package access according to policy;
- optional Project-local service network;
- explicit denial of control-plane/internal privileged networks;
- denial of cloud/host metadata endpoints unless a documented trusted component specifically requires them;
- isolation from other Project runtime networks.

The exact firewall/container/network implementation remains open.

**KSC-REQ-050** — Network reachability must not depend only on the agent choosing not to call an internal address.

---

# 30. Repository and Filesystem Security

## 30.1 Canonical workspace mount

A worker receives only the canonical workspace for the target Project plus explicitly required immutable engine/runtime resources.

It must not receive a broad projects-root mount.

## 30.2 Path construction

User display names and repository names must not become trusted filesystem paths.

Stable internal identifiers and safe path joining are required.

## 30.3 Symlinks

Imported/generated repositories can contain symlinks.

File browsing, archive export, artifact collection, and runtime mounting must prevent symlink traversal from exposing host/control-plane files.

## 30.4 Archive extraction

Any future uploaded archive extraction must defend against:

- `../` traversal;
- absolute paths;
- malicious symlinks;
- device/special files where unsupported.

## 30.5 Source download

Clean source packaging must operate from the canonical workspace with safe path traversal rules.

It must not accidentally include:

- platform credential stores;
- worker runtime directories;
- engine runtime secret material;
- host files reachable through symlinks.

---

# 31. Imported Repository and Prompt-Injection Boundary

Repository content is untrusted.

A README or source file can tell the agent to:

- print environment variables;
- search for credentials;
- upload files;
- disable tests.

Kallula's mechanical controls therefore live outside model obedience.

Security rules that must not depend on prompt compliance include:

- secret non-exposure;
- filesystem isolation;
- network isolation;
- GitHub token isolation;
- control-plane authorization;
- verification gates.

Prompt/skill guidance may reinforce these boundaries but cannot replace them.

---

# 32. Dependency and Build Execution

Generated/imported projects may execute dependency installation and build hooks.

Those commands are untrusted workload.

The later Execution Environment design must:

- run them inside the worker/project sandbox;
- apply resource limits;
- apply network policy;
- prevent host privilege escalation;
- prevent access to control-plane secrets.

Kallula does not claim that dependency code is trustworthy because it came from a package registry.

---

# 33. Logging Security Model

Logs are separated into:

- normalized Product Activity;
- engine/adapter diagnostics;
- application runtime logs;
- platform telemetry;
- security audit records.

Each channel has its own content expectations and retention policy.

## 33.1 Prevention first

Components should avoid logging:

- request bodies containing secrets;
- full environments;
- Authorization headers;
- cookies;
- credential objects containing plaintext;
- third-party tokens;
- encryption keys.

## 33.2 Structured logging

Use structured fields that deliberately select safe metadata.

Do not log arbitrary serialized request/session objects.

---

# 34. Redaction Architecture

Redaction is required at trust-boundary ingestion points.

## 34.1 Known-secret registry

When a trusted component temporarily materializes plaintext secrets, the log/redaction subsystem may register protected values/fingerprints for the relevant scope without persisting the raw values as audit metadata.

## 34.2 Redaction before persistence

For controlled log channels, redact before persistent storage when practical.

This includes:

- application runtime logs;
- worker stdout/stderr captured by Kallula;
- integration command output;
- provider diagnostics.

## 34.3 Pattern detection

Redaction may also detect common credential/token patterns as defense in depth.

Pattern matching cannot be the only protection.

## 34.4 Encoded variants

Where practical and bounded, redaction should account for common accidental transformations of known secrets, such as:

- URL encoding;
- common authorization prefixes.

Do not attempt unbounded transformations that make logging unreliable.

## 34.5 Truncation

Truncation occurs **after** secret redaction where possible.

Otherwise truncation could preserve only the sensitive portion and defeat context-aware redaction.

## 34.6 Native workspace artifacts

Kallula cannot blindly rewrite source/native engine artifacts to redact suspected secrets because those files may be product state.

Instead:

- prevent Kallula-managed secrets from entering the agent;
- scan/flag suspicious values before display/export/publish when appropriate;
- redact controlled log/evidence views;
- do not mutate canonical source silently.

---

# 35. Secret Scanning of Source and Artifacts

Secret scanning is a detection layer, not a substitute for secret isolation.

The system should eventually scan:

- imported source;
- generated source before remote publish;
- selected artifacts/logs;
- clean download packages where appropriate.

Outcomes may include:

- warning;
- publish block for high-confidence platform-owned secret leakage;
- user confirmation for suspected user-owned repository secrets.

Exact scanner/tool choice is open.

Kallula must never silently delete or replace source code based solely on heuristic scanning.

---

# 36. Error Handling

Security-sensitive errors shown to users should be useful without exposing secret material.

Example:

```text
GitHub authorization failed for this repository.
Reconnect GitHub or update repository permissions.
```

Not:

```text
Token ghp_... was rejected.
```

Internal errors:

- may include safe correlation IDs;
- may identify Credential ID/version;
- must not contain plaintext.

---

# 37. Audit Model

Audit records are durable security history distinct from ordinary Activity.

## 37.1 Required fields

Where applicable:

- timestamp;
- actor principal;
- action;
- target type/ID;
- Project/Run relationship;
- outcome;
- reason/category;
- request/correlation ID;
- source/session metadata appropriate to privacy policy;
- credential **identity/version ID**, never value.

## 37.2 Audited actions

At minimum:

- login/logout/security-relevant auth failures where available;
- Credential created;
- Credential replaced/rotated;
- Credential deleted/revoked;
- Project Credential assigned/unassigned;
- integration connected/disconnected;
- GitHub installation/repository authorization changed;
- publish/push/PR requested and result;
- provider credential/configuration changed;
- Engine Installation security compatibility status changed;
- secret runtime grant/injection issued;
- sensitive operation denied by policy;
- root/KEK rotation;
- privileged settings changes.

## 37.3 Audit integrity

Audit records should be append-oriented.

Normal product users should not be able to edit past audit entries.

---

# 38. Security Events vs Product Activity

A security event may also produce user-visible Activity, but the two are not interchangeable.

Example:

```text
Product Activity:
GitHub publish completed.

Security Audit:
actor P123 requested publish of Project X Run 15 to repo Y;
installation Z; result success; token not recorded.
```

The Activity feed remains readable; audit keeps security attribution.

---

# 39. Credential Validation

Kallula may validate some credentials against their provider.

Validation must:

- happen from a trusted component;
- avoid logging the secret;
- use the narrowest safe operation;
- record only success/failure metadata;
- not silently broaden permissions.

A failed validation does not return provider raw response if it contains sensitive headers/data.

---

# 40. Credential Rotation Semantics

## 40.1 Replace

User replacement activates a new value version.

## 40.2 Active processes

Rotation does not retroactively erase plaintext already materialized inside a currently running process.

Therefore security-sensitive credential rotation should allow:

- warning that active runtimes may still hold the previous value;
- stopping/restarting affected runtime/Preview where needed.

Exact restart automation is deferred to Execution Environment design.

## 40.3 Revocation

When compromise is suspected:

1. revoke/rotate at external provider if applicable;
2. disable Kallula use;
3. stop/restart affected runtimes;
4. investigate audit/log/source exposure;
5. replace stored value;
6. confirm redaction/scanning.

---

# 41. Credential Deletion Semantics

Deletion is stronger than unassignment.

Unassignment:

- Project may no longer request use;
- credential remains available for other authorized scopes.

Deletion/revocation:

- marks logical Credential unavailable;
- prevents new grants;
- removes/schedules removal of protected ciphertext according to retention policy;
- preserves non-secret audit history.

Historical Runs may continue to display:

```text
Credential: STRIPE_SECRET_KEY
Status: deleted
```

without retaining the value.

---

# 42. Integration Revocation

Disconnecting GitHub must:

- prevent minting new installation authority for the disconnected scope;
- invalidate cached ephemeral tokens where possible;
- preserve local Git history/source;
- mark publish actions unavailable;
- not delete Project source.

If a repository remains locally available, Kallula can still inspect/build it without GitHub authority.

---

# 43. Preview Browser Security

In addition to origin separation:

- Kallula control-plane CSP should not broadly trust Preview origins;
- Preview pages must not be able to navigate privileged Kallula frames without normal browser protections;
- sensitive Kallula responses use appropriate `frame-ancestors`/framing policy;
- Kallula should avoid exposing bearer credentials in URLs;
- Preview access tokens, if used later, must be narrow, short-lived, and scoped to one Preview/session.

Exact headers are implementation details but must satisfy these properties.

---

# 44. Browser Security Headers

Hosted production should use a deliberate baseline including:

- HTTPS enforcement;
- HSTS after deployment/domain readiness;
- CSP appropriate to the frontend;
- anti-framing policy for Kallula control plane;
- `X-Content-Type-Options: nosniff`;
- restrictive referrer policy appropriate to the product;
- secure cookie attributes.

Final header values depend on frontend/Preview implementation and must be security-tested.

---

# 45. CORS and Cross-Origin Access

Control-plane APIs should not use permissive `*` CORS for authenticated requests.

Allowed origins are explicit.

Preview origin is not automatically an allowed control-plane API origin.

Cross-origin integration flows must be explicitly designed rather than enabled globally.

---

# 46. SSRF and Internal Service Protection

Untrusted code can attempt network requests.

The worker/Preview network policy must prevent access to:

- cloud instance metadata endpoints;
- credential service;
- database;
- Runner/admin interfaces;
- other Project networks;
- host-management services.

If the product later supports URL-fetching features in trusted control-plane components, those components require separate SSRF protections.

---

# 47. Secret Use in Commands

Secrets must not be inserted into shell command strings when avoidable.

Prefer:

- target-process environment;
- file descriptor/stdin mechanisms;
- dedicated provider SDK/session interfaces;
- ephemeral credential helper.

If command-line use is unavoidable for a provider/tool, the risk must be documented because process listings/history may expose arguments.

---

# 48. Temporary Files

Trusted components that temporarily materialize secret files must:

- use restrictive permissions;
- use a directory inaccessible to Project code where possible;
- avoid canonical workspace;
- remove them promptly;
- never Git-add them;
- never include them in source download;
- ensure crash cleanup/reconciliation.

Prefer avoiding temporary plaintext files when feasible.

---

# 49. Metrics and Tracing

Metrics/traces must not use as labels/attributes:

- secret values;
- Authorization headers;
- session IDs;
- full prompts/source by default;
- credential plaintext.

Use stable IDs and bounded categorical metadata.

Prompt/source observability, if ever enabled, is sensitive content and requires explicit retention/access policy.

---

# 50. Data Retention

Security design distinguishes:

- credential ciphertext;
- credential metadata;
- audit records;
- Run logs/evidence;
- Project source;
- Preview runtime logs.

The exact retention durations remain a product/operations decision.

However:

- secret values are not retained in normal logs;
- deleted credentials must not be recoverable from ordinary read APIs;
- backups containing old ciphertext remain subject to key/retention policy;
- audit history may outlive deleted credential ciphertext because it contains no secret value.

---

# 51. Backup and Restore Security

A complete secure restore requires coordinated recovery of:

- control-plane database;
- canonical workspaces;
- Run Engine Runtime state where required;
- credential ciphertext;
- credential key-provider/KEK versions.

Restore testing must confirm:

- secrets decrypt only with authorized key material;
- ownership remains intact;
- deleted/revoked status is preserved;
- no backup restores a credential as active when control state says revoked.

---

# 52. Development and Test Environments

## 52.1 No production secrets

Automated tests and normal development environments use fake credentials.

## 52.2 Local fixtures

Fixture secrets must be obviously non-production and safe to commit only when they are intentionally fake.

## 52.3 Security-mode visibility

Development-only relaxations such as HTTP or PAT fallback must be explicit in configuration and visible in diagnostics.

They must not silently activate in production mode.

## 52.4 Test isolation

Security tests may intentionally seed canary secrets and assert they do not appear in:

- child environments;
- logs;
- events;
- artifacts;
- Git history;
- source export.

---

# 53. Engine Installation Security Compatibility

An Engine Installation is not considered supported until security-relevant compatibility checks pass.

Checks include:

- child environment isolation;
- immutable engine installation;
- external workspace containment;
- provider auth exposure model;
- no platform credential requirement;
- Run-scoped mutable learning assets;
- logs/evidence capture through redaction boundaries;
- absence of GitHub authority inside agent environment.

Compatibility status should include a security dimension.

A revision that breaks secret isolation cannot become default merely because functional tests pass.

---

# 54. Provider and Engine Configuration Governance

User-editable Agent Profiles may change:

- provider;
- model;
- supported thinking;
- permitted behavior/skills.

But security policy may reject a configuration if:

- provider authentication cannot be scoped safely;
- model/tool integration requires broad host credentials;
- required network access violates policy;
- runtime cannot satisfy environment isolation.

Security validation is therefore part of Agent Profile/Engine capability validation.

---

# 55. Security UX Requirements

The UX specification remains authoritative for presentation.

Security-specific requirements include:

- no secret reveal after storage;
- secret inputs never pre-populate with existing value;
- replacing a credential uses a fresh input;
- delete/replace/assignment actions show affected Projects;
- integration permissions are understandable;
- development-only insecure modes are visibly marked;
- Preview shows that it is isolated/untrusted application content where useful;
- compatibility/security failures expose actionable reason without raw secrets.

---

# 56. Security Operations and Compromise Response

Kallula must support an operator playbook for suspected leakage.

## 56.1 Suspected Project credential leak

1. disable future grants;
2. rotate/revoke at provider;
3. stop affected runtime if appropriate;
4. scan source/logs/artifacts;
5. replace stored value;
6. review audit history;
7. restart with new credential if safe.

## 56.2 Suspected GitHub credential leak

For GitHub App model:

- rotate App private key/secret as applicable;
- revoke affected installation/token;
- inspect publish audit;
- do not rely on token expiry alone if broader material leaked.

## 56.3 Suspected KEK compromise

- introduce new KEK;
- re-wrap DEKs;
- revoke old key;
- rotate especially sensitive upstream credentials as risk dictates;
- audit database/backup access;
- document affected interval.

## 56.4 Worker compromise

- terminate Attempt;
- revoke ephemeral grants;
- mark Attempt security-failed;
- preserve safe evidence subject to redaction;
- reconcile canonical workspace;
- do not automatically resume until policy permits.

---

# 57. Security Failure Classification

Useful normalized classes include:

```text
AUTHENTICATION_FAILED
AUTHORIZATION_DENIED
CREDENTIAL_UNAVAILABLE
CREDENTIAL_REVOKED
DECRYPTION_KEY_UNAVAILABLE
PROVIDER_AUTH_FAILED
INTEGRATION_AUTH_FAILED
SECURITY_POLICY_DENIED
PREVIEW_ISOLATION_FAILED
WORKER_ISOLATION_FAILED
SECRET_LEAK_SUSPECTED
```

Exact API enums belong to the API/Data Contract Specification.

Security failure classes must never include secret content.

---

# 58. Security Audit Acceptance Requirements

Security audit coverage must be testable.

Examples:

```text
Credential replaced
  ↓
audit entry has actor + credential ID + version ID
  ↓
no value in audit payload
```

```text
GitHub publish
  ↓
trusted integration obtains ephemeral token
  ↓
push completes
  ↓
audit records repository + actor + result
  ↓
token absent from log/audit/git config
```

---

# 59. Security Acceptance Criteria

## AC-SEC-001 — Database-only compromise is insufficient

A copy of the control-plane database containing credential ciphertext cannot decrypt secrets without separate key-provider/KEK material.

## AC-SEC-002 — No normal reveal API

After credential creation, normal read/list responses contain metadata only and no plaintext/reversible secret.

## AC-SEC-003 — Root key separation

The active root/KEK is not stored as ordinary database data beside encrypted credentials.

## AC-SEC-004 — Authenticated encryption

Tampering with credential ciphertext or bound metadata causes decryption failure rather than silently producing plaintext.

## AC-SEC-005 — Browser token storage

Hosted Kallula does not need a long-lived bearer authentication token in browser `localStorage`.

## AC-SEC-006 — Object authorization

A principal cannot access another owner's Project/Credential merely by guessing or supplying its ID.

## AC-SEC-007 — CSRF protection

Cookie-authenticated state-changing browser operations reject requests that fail configured CSRF/origin protections.

## AC-SEC-008 — Parent environment canary isolation

A canary secret present in the control-plane/worker parent environment is absent from the Pi/agent child environment unless explicitly authorized.

## AC-SEC-009 — No control DB credential in worker

Execution Worker/Siesta/Pi environments do not contain Kallula control database credentials.

## AC-SEC-010 — No GitHub credential in agent

Siesta/Pi does not receive GitHub App private key, installation token, or broad PAT for local coding/Git work.

## AC-SEC-011 — GitHub remote cleanliness

Imported/published repository remote URLs and Git configuration do not persist authentication tokens.

## AC-SEC-012 — Short-lived GitHub authority

Hosted GitHub push/PR operations use trusted integration authority that can be regenerated/revoked without persisting long-lived installation tokens in Project state.

## AC-SEC-013 — Project secret opt-in

Assigning a Project Credential does not automatically place its plaintext in the coding-agent environment.

## AC-SEC-014 — Runtime-only secret separation

A Project runtime can receive an assigned runtime secret without making the same value available to the general coding-agent shell by default.

## AC-SEC-015 — Secret not in source

A Kallula-managed credential used by a runtime is not written by the platform into the canonical source tree or Git history.

## AC-SEC-016 — Preview cookie isolation

Requests to the Preview origin do not carry Kallula control-plane session cookies.

## AC-SEC-017 — Preview network denial

A Preview application cannot reach configured Kallula privileged internal services or host metadata endpoints.

## AC-SEC-018 — Cross-Project isolation

A worker/Preview for Project A cannot mount/read Project B's workspace or injected secrets through normal platform paths.

## AC-SEC-019 — Log redaction

A canary secret intentionally emitted by an application into a controlled runtime log is redacted before persistent user-visible log storage.

## AC-SEC-020 — Request logging exclusion

Credential create/replace request bodies and Authorization/cookie headers are not captured by normal request logs.

## AC-SEC-021 — Audit non-disclosure

Credential security audit events contain identity/version metadata but never the secret value.

## AC-SEC-022 — Key rotation

A KEK rotation can re-wrap credential DEKs and preserve authorized decryptability without user re-entering every secret.

## AC-SEC-023 — Wrong key fails closed

If required KEK material is unavailable, secret-dependent operations fail with a security error rather than starting with missing/garbled secrets.

## AC-SEC-024 — Credential revocation

After a Credential is revoked/deleted, Kallula refuses new grants/injections for it.

## AC-SEC-025 — Active-runtime rotation warning

Replacing/revoking a credential that may already be materialized into an active runtime produces an explicit affected-runtime state/notification or restart requirement.

## AC-SEC-026 — Symlink-safe export

Source export cannot follow a Project symlink to package host/control-plane files outside the canonical workspace.

## AC-SEC-027 — Archive traversal protection

Any archive extraction/import implementation rejects paths that escape its intended extraction root.

## AC-SEC-028 — Security compatibility gating

An Engine Installation/provider combination that fails child-environment secret-isolation tests cannot become supported/default.

## AC-SEC-029 — Development fallback separation

Development-only PAT/HTTP/local-key modes cannot silently activate under production configuration.

## AC-SEC-030 — Backup/key separation

A standard data backup does not contain the only plaintext key material required to decrypt its credential ciphertext.

## AC-SEC-031 — Security event attribution

Security-sensitive commands record the authenticated actor and target without recording credentials.

## AC-SEC-032 — Preview origin is not API origin

Preview content is not automatically authorized as a browser origin for authenticated control-plane API calls.

## AC-SEC-033 — Provider credential scope

A model-provider credential cannot be used as GitHub/control-plane authority merely because it is available for model invocation.

## AC-SEC-034 — Failed validation does not leak

Credential/provider validation errors never return the submitted plaintext or sensitive provider headers.

## AC-SEC-035 — Secret scanning does not silently mutate source

Heuristic secret detection may warn/block according to policy but does not rewrite canonical Project source without an explicit user operation.

---

# 60. PRD Traceability

| PRD area | Security resolution |
|---|---|
| §6.8 Credentials are capabilities | §§11–24 |
| §11 Credential model | §§11–18 |
| §17.8 Environment boundary | §§20–24 |
| §18.6 GitHub publish | §§25–27 |
| §18.8 Credential creation | §§12–16 |
| §20 Run reproducibility | §18 |
| §21 Security Requirements | Entire document |
| §21.1 Trust boundaries | §§6–8 |
| §21.2 Least privilege | §§19–24, 28–32 |
| §21.3 Environment sanitization | §§20–22 |
| §21.4 Credential encryption | §§13–15 |
| §21.5 No reveal | §§12, 16 |
| §21.6 Redaction | §§33–35 |
| §21.7 Preview security | §§28–29, 43–46 |
| §21.8 Model privacy | §§22, 31, 49 |
| §24.2 Audit records | §§37–38 |
| §26.4 Backupability | §§14, 50–51 |
| KAL-FR-230–243 | §§11–24, 40–41 |
| KAL-NFR-SEC-* | Entire document |
| §29.8 Secret isolation | §§8, 20–24, 59 |

---

# 61. Architecture Traceability

| Architecture area | Security resolution |
|---|---|
| §8 Credentials/Integrations concepts | §§11–18, 25–27 |
| §20 Execution ownership | §§20, 29–32 |
| §35 Engine Installation | §§22, 53–54 |
| §39 Mutable engine assets | secret separation maintained |
| §42 Trust boundaries | §§6–8 |
| §42.1 Browser untrusted | §§9–10, 43–45 |
| §42.2 Worker lacks control authority | §§20–24, 29–32 |
| §42.3 Adapter privileged | §§20–22 |
| §42.4 Preview untrusted | §§28–29, 43–46 |
| §42.5 Trusted integrations separate | §§25–27 |
| §45 Backup/restore | §§14, 50–51 |
| §47 Auditability | §§37–38 |
| Invariant K — Secret isolation | §§8, 20–24 |

---

# 62. Siesta Adaptation Traceability

| Adaptation area | Security resolution |
|---|---|
| §26 Agent Slot configuration | security-valid provider combinations |
| §29 Run Engine Runtime | no long-lived platform secrets in mutable runtime |
| §31 Child-process isolation | §§20–22 |
| §31.3 Provider credentials | §22 |
| §32 Pi diagnostics | §§33–35 |
| §33 Git ownership | §§25–27 |
| §37 Capability manifest | security compatibility dimension |
| §43.10 Environment isolation | §59 acceptance tests |
| §47 Security boundary notes | §§6–8, 20–29 |
| AC-KSA-014 | AC-SEC-008–014 |

---

# 63. UX Traceability

| UX area | Security resolution |
|---|---|
| Authentication | §9 |
| Global/Project Credentials | §§11–18, 40–41 |
| Integrations | §§25–27, 42 |
| Engine & System | §§53–54 |
| Runtime Logs | §§33–35 |
| Preview | §§28, 43–46 |
| §52 Security/privacy constraints | Entire document |
| AC-UX-015 | §§12, 16 |
| mobile/desktop secret workflows | metadata-only after storage |

---

# 64. Deliberately Open Security Implementation Decisions

This specification fixes the security **semantics and invariants** while leaving replaceable mechanisms open.

Still open:

1. concrete authentication provider for the first deployment;
2. exact server-side session store implementation;
3. exact AEAD library/primitive selection from the allowed class;
4. exact KeyProvider implementation: protected local key, OS secret facility, or external KMS;
5. exact production secrets manager/storage product;
6. exact credential table/schema/API shape;
7. exact worker sandbox/container technology;
8. exact firewall/network-policy technology;
9. exact Preview domain names and routing technology;
10. exact Preview access-token mechanism;
11. exact redaction/scanning library;
12. exact log retention durations;
13. exact audit storage technology and retention;
14. exact backup product/storage;
15. exact GitHub App permission matrix after final import/publish feature set is frozen;
16. exact model-provider authentication mechanism per provider;
17. whether a future Secret Execution Broker is built;
18. exact low-level secret transport primitive (service environment vs in-memory file/FD) within the now-defined service-scoped runtime injection model.

These choices must satisfy this document rather than redefine its trust model.

---

# 65. Implementation Status

The implementation plan now exists:

> [`Kallula — Implementation Plan.md`](./Kallula%20%E2%80%94%20Implementation%20Plan.md)

Use that document to sequence development and select the first-release implementation choices.

No more architecture document is required before coding starts.

The **Test & Compatibility Strategy** is still required before release. It is intentionally deferred until the implementation has real testable seams, runtime behavior, and compatibility fixtures.


# Appendix A — Credential Exposure Matrix

| Credential class | Browser | Control Plane | Credential Service | Worker | Siesta/Pi | App Runtime | Preview App | Integration Executor |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Root/KEK | No | Prefer no direct | Yes | No | No | No | No | No |
| Control DB | No | Required service only | No | No | No | No | No | No |
| GitHub App private key | No | Prefer integration boundary | Optional encrypted storage | No | No | No | No | Yes |
| GitHub installation token | No | No normal persistence | No | No | No | No | No | Ephemeral |
| Model provider credential | No | Metadata/config | Protected | Maybe narrow broker path | Only if explicitly required | No | No | Provider integration only |
| Project runtime credential | Entry only | Metadata/policy | Yes | No by default | No by default | If assigned | Through app runtime only | No |
| Browser session | Cookie | Session validation | No | No | No | No | Never | No |

“Entry only” means plaintext is submitted during create/replace but is not retrievable afterward.

---

# Appendix B — Security Boundary Checklist

Before implementation is considered production-capable:

- [ ] browser sessions are Secure/HttpOnly and server-managed;
- [ ] CSRF/origin protections are tested;
- [ ] object authorization is tested;
- [ ] credential values use envelope encryption;
- [ ] root/KEK is outside DB;
- [ ] credential read APIs are metadata-only;
- [ ] request logs exclude secret bodies/headers;
- [ ] worker parent environment is allowlisted;
- [ ] Pi child environment is allowlisted;
- [ ] control DB credentials absent from worker;
- [ ] GitHub authority absent from agent;
- [ ] Project runtime secrets absent from agent by default;
- [ ] Preview uses separate trusted boundary/origin;
- [ ] control-plane cookies never reach Preview;
- [ ] Preview cannot reach privileged internal network;
- [ ] cross-Project workspace mounts are impossible by normal path;
- [ ] symlink-safe source browse/export exists;
- [ ] audit records cover credential/integration operations;
- [ ] redaction happens before persistent controlled log storage;
- [ ] backup/KEK recovery is tested;
- [ ] development-only insecure modes cannot run silently in production;
- [ ] Engine Installation security compatibility tests pass.

---

# Appendix C — Security Decision Summary

| Topic | Decision |
|---|---|
| Browser auth state | server-managed session; no long-lived localStorage bearer token |
| Secret read behavior | metadata-only after create/replace |
| At-rest encryption | envelope encryption with per-value DEK |
| Root key | separate KeyProvider/KEK outside normal DB |
| Worker env | explicit allowlist |
| Pi env | explicit allowlist; no wholesale `os.environ` inheritance |
| Agent Project secrets | denied by default |
| App runtime secrets | explicit Project assignment + trusted runtime injection |
| GitHub production auth | GitHub App installation model |
| GitHub token exposure | trusted integration only, short-lived |
| Preview | untrusted workload on separate origin/security boundary |
| Redaction | defense in depth; before controlled log persistence |
| Source secret scanning | detect/warn/block by policy, never silently rewrite source |
| Audit | append-oriented metadata, no values |
| Security compatibility | required before Engine Installation becomes supported/default |

---

# Final Security Rule

> **Kallula must never grant an autonomous process authority merely because that authority is convenient for the parent process. Every secret, network path, filesystem mount, integration permission, and browser trust relationship must cross an explicit, minimal, auditable boundary.**


The **Test & Compatibility Strategy** remains required before release, but is intentionally deferred until implementation choices and testable seams are concrete.
