import asyncio

from persistence.attempts import create_attempt
from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory
from persistence.models import Principal, Project, Run


async def prepare(database_url: str):
    engine = create_db_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine


def test_attempt_ordinals_increment(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'attempts.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                principal = Principal(
                    auth_provider="development", auth_subject="dev", display_name="Dev"
                )
                session.add(principal)
                await session.flush()
                project = Project(owner_id=principal.id, display_name="Project")
                session.add(project)
                await session.flush()
                run = Run(project_id=project.id, ordinal=1, objective="Build it")
                session.add(run)
                await session.flush()

                first = await create_attempt(session, run)
                second = await create_attempt(session, run)

                assert first.ordinal == 1
                assert second.ordinal == 2
                assert first.state.value == "ALLOCATED"
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())
