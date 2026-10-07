import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory
from persistence.leases import (
    LeaseConflictError,
    acquire,
    clear_expired,
    release,
    renew,
)
from persistence.models import Principal, Project


async def prepare(database_url: str):
    engine = create_db_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine


async def seed_project(session) -> Project:
    principal = Principal(
        auth_provider="development", auth_subject="dev", display_name="Dev"
    )
    session.add(principal)
    await session.flush()
    project = Project(owner_id=principal.id, display_name="Project")
    session.add(project)
    await session.flush()
    return project


def test_one_valid_lease_per_project(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'leases.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                project = await seed_project(session)
                lease = await acquire(
                    session, project_id=project.id, holder_id="worker-a"
                )
                assert lease.lease_epoch == 1
                with pytest.raises(LeaseConflictError):
                    await acquire(session, project_id=project.id, holder_id="worker-b")
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_expired_lease_can_be_reacquired_with_new_epoch(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'leases.db'}")
        factory = create_session_factory(engine)
        start = datetime(2026, 1, 1, tzinfo=UTC)
        try:
            async with factory() as session:
                project = await seed_project(session)
                await acquire(
                    session,
                    project_id=project.id,
                    holder_id="worker-a",
                    now=start,
                    duration=timedelta(minutes=1),
                )
                await session.commit()

            async with factory() as session:
                lease = await acquire(
                    session,
                    project_id=project.id,
                    holder_id="worker-b",
                    now=start + timedelta(minutes=2),
                )
                assert lease.lease_epoch == 2
                assert lease.holder_id == "worker-b"
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_stale_epoch_cannot_renew_or_release(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'leases.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                project = await seed_project(session)
                await acquire(session, project_id=project.id, holder_id="worker-a")
                await session.commit()

            async with factory() as session:
                with pytest.raises(LeaseConflictError):
                    await renew(
                        session,
                        project_id=project.id,
                        holder_id="worker-a",
                        lease_epoch=99,
                    )
                with pytest.raises(LeaseConflictError):
                    await release(
                        session,
                        project_id=project.id,
                        holder_id="worker-b",
                        lease_epoch=1,
                    )
                renewed = await renew(
                    session,
                    project_id=project.id,
                    holder_id="worker-a",
                    lease_epoch=1,
                )
                assert renewed.lease_epoch == 1
                await release(
                    session, project_id=project.id, holder_id="worker-a", lease_epoch=1
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_clear_expired(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'leases.db'}")
        factory = create_session_factory(engine)
        start = datetime(2026, 1, 1, tzinfo=UTC)
        try:
            async with factory() as session:
                project = await seed_project(session)
                await acquire(
                    session,
                    project_id=project.id,
                    holder_id="worker-a",
                    now=start,
                    duration=timedelta(seconds=30),
                )
                await session.commit()

            async with factory() as session:
                cleared = await clear_expired(
                    session, project_id=project.id, now=start + timedelta(minutes=1)
                )
                assert cleared is True
                cleared_again = await clear_expired(
                    session, project_id=project.id, now=start + timedelta(minutes=1)
                )
                assert cleared_again is False
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())
