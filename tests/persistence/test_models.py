import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy import text as sql_text
from sqlalchemy.exc import IntegrityError

from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory
from persistence.models import (
    Command,
    CommandState,
    ExecutionAttempt,
    IdempotencyRecord,
    Principal,
    Project,
    ProjectExecutionLease,
    Run,
    RunConfigSnapshot,
    RunControlState,
    Workspace,
    WorkspaceStatus,
)


async def prepare(database_url: str):
    engine = create_db_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine


def make_url(tmp_path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'schema.db'}"


async def seed(session) -> dict[str, Principal | Project]:
    principal = Principal(
        auth_provider="development",
        auth_subject="dev-principal",
        display_name="Development User",
    )
    session.add(principal)
    await session.flush()

    project = Project(owner_id=principal.id, display_name="Expense Tracker")
    session.add(project)
    await session.flush()
    return {"principal": principal, "project": project}


def test_schema_round_trip(tmp_path):
    async def scenario():
        engine = await prepare(make_url(tmp_path))
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                ids = await seed(session)
                project = ids["project"]
                principal = ids["principal"]

                workspace = Workspace(
                    project_id=project.id,
                    storage_driver="local",
                    storage_key="projects/expense-tracker",
                    status=WorkspaceStatus.READY,
                )
                session.add(workspace)
                await session.flush()
                project.workspace_id = workspace.id

                run = Run(project_id=project.id, ordinal=1, objective="Build it")
                session.add(run)
                await session.flush()

                snapshot = RunConfigSnapshot(
                    run_id=run.id,
                    content_hash="hash-1",
                    engineering_preferences_json={"style": "concise"},
                )
                session.add(snapshot)
                await session.flush()
                run.effective_config_snapshot_id = snapshot.id

                attempt = ExecutionAttempt(run_id=run.id, ordinal=1)
                session.add(attempt)
                await session.flush()
                run.active_attempt_id = attempt.id

                lease = ProjectExecutionLease(
                    project_id=project.id,
                    run_id=run.id,
                    attempt_id=attempt.id,
                    holder_id="coordinator-1",
                    expires_at=datetime.now(UTC) + timedelta(minutes=5),
                )
                session.add(lease)

                command = Command(
                    actor_principal_id=principal.id,
                    command_type="START_RUN",
                    target_type="RUN",
                    target_id=run.id,
                    request_json={},
                    request_hash="request-hash",
                    idempotency_key="key-1",
                )
                session.add(command)

                record = IdempotencyRecord(
                    principal_id=principal.id,
                    method="POST",
                    canonical_path="/api/v1/projects",
                    idempotency_key="key-1",
                    request_hash="request-hash",
                    response_status=201,
                    response_resource_ref=project.id,
                    expires_at=datetime.now(UTC) + timedelta(hours=24),
                )
                session.add(record)
                await session.commit()

            async with factory() as session:
                stored_run = (
                    await session.execute(select(Run).where(Run.id == run.id))
                ).scalar_one()
                assert stored_run.control_state == RunControlState.QUEUED
                assert stored_run.effective_config_snapshot_id == snapshot.id
                assert stored_run.active_attempt_id == attempt.id

                stored_snapshot = (
                    await session.execute(
                        select(RunConfigSnapshot).where(
                            RunConfigSnapshot.run_id == run.id
                        )
                    )
                ).scalar_one()
                assert stored_snapshot.content_hash == "hash-1"

                stored_lease = (
                    await session.execute(select(ProjectExecutionLease))
                ).scalar_one()
                assert stored_lease.lease_epoch == 1
                assert stored_lease.holder_id == "coordinator-1"

                stored_command = (
                    await session.execute(
                        select(Command).where(Command.id == command.id)
                    )
                ).scalar_one()
                assert stored_command.state == CommandState.ACCEPTED
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_principal_provider_and_subject_are_unique(tmp_path):
    async def scenario():
        engine = await prepare(make_url(tmp_path))
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                session.add(
                    Principal(
                        auth_provider="development",
                        auth_subject="dev",
                        display_name="One",
                    )
                )
                await session.commit()
            async with factory() as session:
                session.add(
                    Principal(
                        auth_provider="development",
                        auth_subject="dev",
                        display_name="Two",
                    )
                )
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_workspace_is_unique_per_project(tmp_path):
    async def scenario():
        engine = await prepare(make_url(tmp_path))
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                await seed(session)
                await session.commit()
            async with factory() as session:
                project = (await session.execute(select(Project))).scalar_one()
                session.add(
                    Workspace(
                        project_id=project.id,
                        storage_driver="local",
                        storage_key="a",
                    )
                )
                session.add(
                    Workspace(
                        project_id=project.id,
                        storage_driver="local",
                        storage_key="b",
                    )
                )
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_run_ordinal_is_unique_per_project(tmp_path):
    async def scenario():
        engine = await prepare(make_url(tmp_path))
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                await seed(session)
                await session.commit()
            async with factory() as session:
                project = (await session.execute(select(Project))).scalar_one()
                session.add(Run(project_id=project.id, ordinal=1, objective="a"))
                session.add(Run(project_id=project.id, ordinal=1, objective="b"))
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_config_snapshot_is_unique_per_run(tmp_path):
    async def scenario():
        engine = await prepare(make_url(tmp_path))
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                ids = await seed(session)
                run = Run(project_id=ids["project"].id, ordinal=1, objective="a")
                session.add(run)
                await session.flush()
                session.add(RunConfigSnapshot(run_id=run.id, content_hash="h1"))
                session.add(RunConfigSnapshot(run_id=run.id, content_hash="h2"))
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_attempt_ordinal_is_unique_per_run(tmp_path):
    async def scenario():
        engine = await prepare(make_url(tmp_path))
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                ids = await seed(session)
                run = Run(project_id=ids["project"].id, ordinal=1, objective="a")
                session.add(run)
                await session.flush()
                session.add(ExecutionAttempt(run_id=run.id, ordinal=1))
                session.add(ExecutionAttempt(run_id=run.id, ordinal=1))
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_lease_is_single_per_project(tmp_path):
    async def scenario():
        engine = await prepare(make_url(tmp_path))
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                project = (await seed(session))["project"]
                expires = datetime.now(UTC) + timedelta(minutes=5)
                session.add(
                    ProjectExecutionLease(
                        project_id=project.id, holder_id="one", expires_at=expires
                    )
                )
                session.add(
                    ProjectExecutionLease(
                        project_id=project.id, holder_id="two", expires_at=expires
                    )
                )
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_command_idempotency_is_unique_per_actor_and_type(tmp_path):
    async def scenario():
        engine = await prepare(make_url(tmp_path))
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                principal = (await seed(session))["principal"]

                def command() -> Command:
                    return Command(
                        actor_principal_id=principal.id,
                        command_type="START_RUN",
                        target_type="RUN",
                        target_id="run-1",
                        request_json={},
                        request_hash="h",
                        idempotency_key="same-key",
                    )

                session.add(command())
                session.add(command())
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_idempotency_scope_is_unique(tmp_path):
    async def scenario():
        engine = await prepare(make_url(tmp_path))
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                principal = (await seed(session))["principal"]
                expires = datetime.now(UTC) + timedelta(hours=24)

                def record() -> IdempotencyRecord:
                    return IdempotencyRecord(
                        principal_id=principal.id,
                        method="POST",
                        canonical_path="/api/v1/projects",
                        idempotency_key="key",
                        request_hash="h",
                        response_status=201,
                        expires_at=expires,
                    )

                session.add(record())
                session.add(record())
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_run_state_check_rejects_unknown_value(tmp_path):
    async def scenario():
        engine = await prepare(make_url(tmp_path))
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                project = (await seed(session))["project"]
                with pytest.raises(IntegrityError):
                    await session.execute(
                        sql_text(
                            "INSERT INTO runs (id, project_id, ordinal, objective, control_state, "
                            "last_event_sequence, version, created_at, updated_at) "
                            "VALUES ('manual-run', :project_id, 9, 'invalid', 'NOT_A_STATE', 0, 1, "
                            "'2026-01-01 00:00:00', '2026-01-01 00:00:00')"
                        ),
                        {"project_id": project.id},
                    )
                    await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())
