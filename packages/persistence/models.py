from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from domain.states import (
    AttemptState,
    CommandState,
    CompatibilityStatus,
    EngineInstallationStatus,
    EventSeverity,
    EventSource,
    OriginType,
    Recoverability,
    RunControlState,
    WorkspaceStatus,
)
from persistence.base import Base


def new_id() -> str:
    return uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class Principal(Base):
    __tablename__ = "principals"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    auth_provider: Mapped[str] = mapped_column(String(64))
    auth_subject: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    version: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (UniqueConstraint("auth_provider", "auth_subject"),)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), unique=True)
    storage_driver: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(512))
    status: Mapped[WorkspaceStatus] = mapped_column(
        Enum(
            WorkspaceStatus,
            name="workspace_status",
            native_enum=False,
            create_constraint=True,
            length=32,
        ),
        default=WorkspaceStatus.INITIALIZING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("principals.id"))
    display_name: Mapped[str] = mapped_column(String(255))
    origin_type: Mapped[OriginType] = mapped_column(
        Enum(
            OriginType,
            name="origin_type",
            native_enum=False,
            create_constraint=True,
            length=32,
        ),
        default=OriginType.NEW_IDEA,
    )
    origin_metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    workspace_id: Mapped[str | None] = mapped_column(String(32))
    workspace_status: Mapped[WorkspaceStatus] = mapped_column(
        Enum(
            WorkspaceStatus,
            name="workspace_status",
            native_enum=False,
            create_constraint=True,
            length=32,
        ),
        default=WorkspaceStatus.INITIALIZING,
    )
    workspace_error_code: Mapped[str | None] = mapped_column(String(64))
    default_engine_policy_json: Mapped[dict] = mapped_column(JSON, default=dict)
    default_agent_profile_version_id: Mapped[str | None] = mapped_column(String(32))
    default_environment_profile_version_id: Mapped[str | None] = mapped_column(
        String(32)
    )
    engineering_preferences_json: Mapped[dict] = mapped_column(JSON, default=dict)
    current_verified_state_id: Mapped[str | None] = mapped_column(String(32))
    current_run_id: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    version: Mapped[int] = mapped_column(Integer, default=1)


class RunConfigSnapshot(Base):
    __tablename__ = "run_config_snapshots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), unique=True)
    engine_installation_id: Mapped[str | None] = mapped_column(String(32))
    capability_manifest_hash: Mapped[str | None] = mapped_column(String(128))
    agent_profile_version_id: Mapped[str | None] = mapped_column(String(32))
    agent_slots_json: Mapped[dict] = mapped_column(JSON, default=dict)
    provider_model_assignments_json: Mapped[dict] = mapped_column(JSON, default=dict)
    reasoning_tool_settings_json: Mapped[dict] = mapped_column(JSON, default=dict)
    engineering_preferences_json: Mapped[dict] = mapped_column(JSON, default=dict)
    skill_identities_json: Mapped[dict] = mapped_column(JSON, default=dict)
    environment_profile_version_id: Mapped[str | None] = mapped_column(String(32))
    permitted_credential_refs_json: Mapped[list] = mapped_column(JSON, default=list)
    starting_git_commit: Mapped[str | None] = mapped_column(String(64))
    starting_git_dirty: Mapped[bool] = mapped_column(Boolean, default=False)
    starting_git_status_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    content_hash: Mapped[str] = mapped_column(String(128))


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    ordinal: Mapped[int] = mapped_column(Integer)
    objective: Mapped[str] = mapped_column(Text)
    control_state: Mapped[RunControlState] = mapped_column(
        Enum(
            RunControlState,
            name="run_control_state",
            native_enum=False,
            create_constraint=True,
            length=32,
        ),
        default=RunControlState.QUEUED,
    )
    current_stage_category: Mapped[str | None] = mapped_column(String(64))
    current_stage_native_id: Mapped[str | None] = mapped_column(String(128))
    current_stage_label: Mapped[str | None] = mapped_column(String(128))
    current_stage_order: Mapped[int | None] = mapped_column(Integer)
    active_work_item_id: Mapped[str | None] = mapped_column(String(32))
    effective_config_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("run_config_snapshots.id")
    )
    engine_installation_id: Mapped[str | None] = mapped_column(String(32))
    environment_snapshot_id: Mapped[str | None] = mapped_column(String(32))
    active_attempt_id: Mapped[str | None] = mapped_column(String(32))
    pending_interaction_id: Mapped[str | None] = mapped_column(String(32))
    last_event_sequence: Mapped[int] = mapped_column(Integer, default=0)
    last_verified_state_id: Mapped[str | None] = mapped_column(String(32))
    failure_class: Mapped[str | None] = mapped_column(String(64))
    failure_code: Mapped[str | None] = mapped_column(String(64))
    failure_summary: Mapped[str | None] = mapped_column(Text)
    recoverability: Mapped[Recoverability | None] = mapped_column(
        Enum(
            Recoverability,
            name="recoverability",
            native_enum=False,
            create_constraint=True,
            length=32,
        )
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    version: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (UniqueConstraint("project_id", "ordinal"),)


class ExecutionAttempt(Base):
    __tablename__ = "execution_attempts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    ordinal: Mapped[int] = mapped_column(Integer)
    state: Mapped[AttemptState] = mapped_column(
        Enum(
            AttemptState,
            name="attempt_state",
            native_enum=False,
            create_constraint=True,
            length=32,
        ),
        default=AttemptState.ALLOCATED,
    )
    worker_runtime_ref: Mapped[str | None] = mapped_column(String(255))
    engine_installation_id: Mapped[str | None] = mapped_column(String(32))
    environment_snapshot_id: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terminal_reason: Mapped[str | None] = mapped_column(String(64))
    observed_stage_category: Mapped[str | None] = mapped_column(String(64))
    observed_engine_state_ref: Mapped[str | None] = mapped_column(String(255))
    log_stream_id: Mapped[str | None] = mapped_column(String(32))

    __table_args__ = (UniqueConstraint("run_id", "ordinal"),)


class ProjectExecutionLease(Base):
    __tablename__ = "project_execution_leases"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"))
    attempt_id: Mapped[str | None] = mapped_column(ForeignKey("execution_attempts.id"))
    holder_id: Mapped[str] = mapped_column(String(255))
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    renewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_epoch: Mapped[int] = mapped_column(Integer, default=1)


class Command(Base):
    __tablename__ = "commands"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    actor_principal_id: Mapped[str] = mapped_column(ForeignKey("principals.id"))
    command_type: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(32))
    state: Mapped[CommandState] = mapped_column(
        Enum(
            CommandState,
            name="command_state",
            native_enum=False,
            create_constraint=True,
            length=32,
        ),
        default=CommandState.ACCEPTED,
    )
    request_json: Mapped[dict] = mapped_column(JSON, default=dict)
    request_hash: Mapped[str] = mapped_column(String(128))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    processing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(64))
    failure_summary: Mapped[str | None] = mapped_column(Text)
    result_refs_json: Mapped[dict] = mapped_column(JSON, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        UniqueConstraint("actor_principal_id", "command_type", "idempotency_key"),
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    principal_id: Mapped[str] = mapped_column(
        ForeignKey("principals.id"), primary_key=True
    )
    method: Mapped[str] = mapped_column(String(16), primary_key=True)
    canonical_path: Mapped[str] = mapped_column(String(512), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(128))
    response_status: Mapped[int] = mapped_column(Integer)
    response_resource_ref: Mapped[str | None] = mapped_column(String(64))
    response_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EngineInstallation(Base):
    __tablename__ = "engine_installations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    engine_family: Mapped[str] = mapped_column(String(32))
    engine_revision: Mapped[str] = mapped_column(String(64))
    adapter_version: Mapped[str] = mapped_column(String(32))
    installation_digest: Mapped[str] = mapped_column(String(128))
    status: Mapped[EngineInstallationStatus] = mapped_column(
        Enum(
            EngineInstallationStatus,
            name="engine_installation_status",
            native_enum=False,
            create_constraint=True,
            length=32,
        ),
        default=EngineInstallationStatus.CANDIDATE,
    )
    default_for_new_runs: Mapped[bool] = mapped_column(Boolean, default=False)
    compatibility_launch: Mapped[CompatibilityStatus] = mapped_column(
        Enum(
            CompatibilityStatus,
            name="compatibility_status_launch",
            native_enum=False,
            create_constraint=True,
            length=16,
        ),
        default=CompatibilityStatus.UNKNOWN,
    )
    compatibility_state_format: Mapped[CompatibilityStatus] = mapped_column(
        Enum(
            CompatibilityStatus,
            name="compatibility_status_state_format",
            native_enum=False,
            create_constraint=True,
            length=16,
        ),
        default=CompatibilityStatus.UNKNOWN,
    )
    compatibility_resume: Mapped[CompatibilityStatus] = mapped_column(
        Enum(
            CompatibilityStatus,
            name="compatibility_status_resume",
            native_enum=False,
            create_constraint=True,
            length=16,
        ),
        default=CompatibilityStatus.UNKNOWN,
    )
    compatibility_security: Mapped[CompatibilityStatus] = mapped_column(
        Enum(
            CompatibilityStatus,
            name="compatibility_status_security",
            native_enum=False,
            create_constraint=True,
            length=16,
        ),
        default=CompatibilityStatus.UNKNOWN,
    )
    compatibility_runtime: Mapped[CompatibilityStatus] = mapped_column(
        Enum(
            CompatibilityStatus,
            name="compatibility_status_runtime",
            native_enum=False,
            create_constraint=True,
            length=16,
        ),
        default=CompatibilityStatus.UNKNOWN,
    )
    capability_manifest_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    sequence: Mapped[int] = mapped_column(Integer)
    attempt_id: Mapped[str | None] = mapped_column(ForeignKey("execution_attempts.id"))
    source: Mapped[EventSource] = mapped_column(
        Enum(
            EventSource,
            name="event_source",
            native_enum=False,
            create_constraint=True,
            length=32,
        )
    )
    source_event_sequence: Mapped[int | None] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(64))
    severity: Mapped[EventSeverity] = mapped_column(
        Enum(
            EventSeverity,
            name="event_severity",
            native_enum=False,
            create_constraint=True,
            length=16,
        ),
        default=EventSeverity.INFO,
    )
    stage_category: Mapped[str | None] = mapped_column(String(64))
    stage_native_id: Mapped[str | None] = mapped_column(String(128))
    stage_label: Mapped[str | None] = mapped_column(String(128))
    stage_order: Mapped[int | None] = mapped_column(Integer)
    work_item_id: Mapped[str | None] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(Text)
    payload_version: Mapped[int] = mapped_column(Integer, default=1)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    artifact_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    __table_args__ = (
        UniqueConstraint("run_id", "sequence"),
        UniqueConstraint("attempt_id", "source_event_sequence"),
    )
