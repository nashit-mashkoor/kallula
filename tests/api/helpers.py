import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from api.main import create_app
from api.settings import Settings
from domain.states import (
    ArtifactClass,
    ArtifactStorageKind,
    CompatibilityStatus,
    EngineInstallationStatus,
    WorkItemState,
    WorkspaceStatus,
)
from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory
from persistence.events import append_event
from persistence.models import (
    Artifact,
    Command,
    EngineInstallation,
    Event,
    Principal,
    Project,
    Run,
    WorkItem,
    Workspace,
)
from runtime.base.storage import resolve_under_root
from runtime.base.workspace import WorkspaceManager


async def _prepare_database(database_url: str) -> None:
    engine = create_db_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


def prepare_database(database_url: str) -> None:
    asyncio.run(_prepare_database(database_url))


def workspace_root_for(database_url: str) -> Path:
    database_path = Path(database_url.removeprefix("sqlite+aiosqlite:///"))
    return database_path.parent / "workspaces"


def build_client(database_url: str, **overrides) -> TestClient:
    overrides.setdefault("workspace_root", workspace_root_for(database_url))
    settings = Settings(
        database_url=database_url, log_level="WARNING", _env_file=None, **overrides
    )
    return TestClient(create_app(settings))


async def _seed_installation(
    database_url: str,
    *,
    status: EngineInstallationStatus = EngineInstallationStatus.SUPPORTED,
    compatibility_launch: CompatibilityStatus = CompatibilityStatus.SUPPORTED,
    default_for_new_runs: bool = True,
) -> str:
    engine = create_db_engine(database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            installation = EngineInstallation(
                engine_family="SIESTA",
                engine_revision="20b149e0734b09730dfd22803d2695776fcf84b8",
                adapter_version="0.1.0",
                installation_digest="sha256:test-installation",
                status=status,
                default_for_new_runs=default_for_new_runs,
                compatibility_launch=compatibility_launch,
                capability_manifest_json={
                    "schema_version": 1,
                    "work_items": True,
                    "verification": True,
                },
            )
            session.add(installation)
            await session.commit()
            return installation.id
    finally:
        await engine.dispose()


def seed_installation(database_url: str, **kwargs) -> str:
    return asyncio.run(_seed_installation(database_url, **kwargs))


async def _seed_work_item(
    database_url: str,
    run_id: str,
    *,
    engine_key: str = "issue:1",
    ordinal: int = 1,
    title: str = "Add hello",
    state: WorkItemState = WorkItemState.PENDING,
) -> str:
    engine = create_db_engine(database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            item = WorkItem(
                run_id=run_id,
                engine_key=engine_key,
                ordinal=ordinal,
                title=title,
                state=state,
            )
            session.add(item)
            await session.commit()
            return item.id
    finally:
        await engine.dispose()


def seed_work_item(database_url: str, run_id: str, **kwargs) -> str:
    return asyncio.run(_seed_work_item(database_url, run_id, **kwargs))


async def _seed_artifact(
    database_url: str,
    *,
    project_id: str,
    run_id: str,
    storage_key: str,
    artifact_class: ArtifactClass = ArtifactClass.SPECIFICATION,
    display_name: str = "Specification",
    media_type: str | None = "text/markdown",
    content: str | None = None,
) -> str:
    workspace_key = f"projects/{project_id}/workspace"
    manager = WorkspaceManager(workspace_root_for(database_url))
    workspace_path = manager.allocate(workspace_key)
    if content is not None:
        path = resolve_under_root(workspace_path, storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    engine = create_db_engine(database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            workspace = (
                await session.execute(
                    select(Workspace).where(Workspace.project_id == project_id)
                )
            ).scalar_one_or_none()
            if workspace is None:
                workspace = Workspace(
                    project_id=project_id,
                    storage_driver="local",
                    storage_key=workspace_key,
                    status=WorkspaceStatus.READY,
                )
                session.add(workspace)
                await session.flush()
            artifact = Artifact(
                project_id=project_id,
                run_id=run_id,
                artifact_class=artifact_class,
                display_name=display_name,
                media_type=media_type,
                storage_kind=ArtifactStorageKind.WORKSPACE_REFERENCE,
                storage_key=storage_key,
            )
            session.add(artifact)
            await session.commit()
            return artifact.id
    finally:
        await engine.dispose()


def seed_artifact(database_url: str, **kwargs) -> str:
    return asyncio.run(_seed_artifact(database_url, **kwargs))


async def _seed_command(database_url: str) -> str:
    engine = create_db_engine(database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            principal = Principal(
                id="dev-principal",
                auth_provider="development",
                auth_subject="dev-principal",
                display_name="Development User",
            )
            session.add(principal)
            command = Command(
                actor_principal_id=principal.id,
                command_type="START_RUN",
                target_type="RUN",
                target_id="run-1",
                request_json={},
                request_hash="hash",
                idempotency_key="key",
            )
            session.add(command)
            await session.commit()
            return command.id
    finally:
        await engine.dispose()


def seed_command(database_url: str) -> str:
    return asyncio.run(_seed_command(database_url))


async def _fetch_events(database_url: str, run_id: str) -> list[tuple[str, int, str]]:
    engine = create_db_engine(database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            events = (
                (
                    await session.execute(
                        select(Event)
                        .where(Event.run_id == run_id)
                        .order_by(Event.sequence)
                    )
                )
                .scalars()
                .all()
            )
            return [
                (event.event_type, event.sequence, event.source.value)
                for event in events
            ]
    finally:
        await engine.dispose()


def fetch_events(database_url: str, run_id: str) -> list[tuple[str, int, str]]:
    return asyncio.run(_fetch_events(database_url, run_id))


async def _seed_run(database_url: str) -> str:
    engine = create_db_engine(database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            principal = Principal(
                id="dev-principal",
                auth_provider="development",
                auth_subject="dev-principal",
                display_name="Development User",
            )
            session.add(principal)
            await session.flush()
            project = Project(owner_id=principal.id, display_name="Project")
            session.add(project)
            await session.flush()
            run = Run(project_id=project.id, ordinal=1, objective="Build it")
            session.add(run)
            await session.flush()
            await session.commit()
            return run.id
    finally:
        await engine.dispose()


def seed_run(database_url: str) -> str:
    return asyncio.run(_seed_run(database_url))


async def _append_run_event(database_url: str, run_id: str, summary: str) -> int:
    engine = create_db_engine(database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            run = (
                await session.execute(select(Run).where(Run.id == run_id))
            ).scalar_one()
            event = await append_event(
                session,
                run,
                event_type="RUN_STARTING",
                category="RUN",
                summary=summary,
            )
            await session.commit()
            return event.sequence
    finally:
        await engine.dispose()


def append_run_event(database_url: str, run_id: str, summary: str) -> int:
    return asyncio.run(_append_run_event(database_url, run_id, summary))


async def _trim_events(
    database_url: str, run_id: str, keep_after_sequence: int
) -> None:
    engine = create_db_engine(database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            await session.execute(
                delete(Event).where(
                    Event.run_id == run_id, Event.sequence <= keep_after_sequence
                )
            )
            await session.commit()
    finally:
        await engine.dispose()


def trim_events(database_url: str, run_id: str, keep_after_sequence: int) -> None:
    asyncio.run(_trim_events(database_url, run_id, keep_after_sequence))
