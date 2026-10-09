import asyncio

from factories import static_factory
from sqlalchemy import select

from coordinator.loop import process_queued_runs
from domain.states import ArtifactClass, ArtifactStorageKind
from engine.base import (
    EngineCapabilities,
    EngineDescriptor,
    EngineEvent,
    EngineIdentity,
    EngineOutcome,
    EngineResult,
)
from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory
from persistence.models import Artifact, Event, Principal, Project, Run


class ArtifactEngine:
    def describe(self) -> EngineDescriptor:
        return EngineDescriptor(
            identity=EngineIdentity(family="FAKE", revision="1", adapter_version="1"),
            capabilities=EngineCapabilities(),
        )

    async def run(self, request, hooks) -> EngineResult:
        payload = {
            "artifact_class": "SPECIFICATION",
            "display_name": "Specification",
            "relative_path": "spec.md",
            "media_type": "text/markdown",
            "size_bytes": 12,
            "content_hash": "sha256:abc123",
            "source_identity": {"git_commit": "deadbeef"},
        }
        await hooks.on_event(
            EngineEvent(
                event_type="ARTIFACT_DISCOVERED",
                category="ARTIFACT",
                summary="Specification recorded.",
                source_event_sequence=1,
                payload=payload,
            )
        )
        await hooks.on_event(
            EngineEvent(
                event_type="ARTIFACT_DISCOVERED",
                category="ARTIFACT",
                summary="Specification recorded again.",
                source_event_sequence=2,
                payload=payload,
            )
        )
        await hooks.on_event(
            EngineEvent(
                event_type="ARTIFACT_DISCOVERED",
                category="ARTIFACT",
                summary="Verification verdict recorded.",
                source_event_sequence=3,
                payload={
                    "artifact_class": "VERIFICATION_EVIDENCE",
                    "display_name": "Verification verdict",
                    "relative_path": "verify_verdict.txt",
                    "media_type": "text/plain",
                },
            )
        )
        return EngineResult(outcome=EngineOutcome.COMPLETED_VERIFIED)


async def prepare(database_url: str):
    engine = create_db_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine


async def seed_queued_run(session) -> Run:
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
    return run


def test_artifact_events_create_deduplicated_artifact_records(tmp_path):
    async def scenario():
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path / 'artifact-events.db'}")
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = await seed_queued_run(session)
                await session.commit()
                run_id = run.id
                project_id = run.project_id

            async with factory() as session:
                processed = await process_queued_runs(
                    session,
                    holder_id="test",
                    engine_factory=static_factory(ArtifactEngine()),
                )
                assert processed == 1

            async with factory() as session:
                artifacts = (
                    (
                        await session.execute(
                            select(Artifact).order_by(Artifact.created_at, Artifact.id)
                        )
                    )
                    .scalars()
                    .all()
                )
                assert len(artifacts) == 2
                specification = next(
                    item
                    for item in artifacts
                    if item.artifact_class is ArtifactClass.SPECIFICATION
                )
                assert specification.project_id == project_id
                assert specification.run_id == run_id
                assert specification.display_name == "Specification"
                assert specification.media_type == "text/markdown"
                assert specification.size_bytes == 12
                assert specification.content_hash == "sha256:abc123"
                assert (
                    specification.storage_kind
                    is ArtifactStorageKind.WORKSPACE_REFERENCE
                )
                assert specification.storage_key == "spec.md"
                assert specification.source_identity_json == {"git_commit": "deadbeef"}

                events = (
                    (
                        await session.execute(
                            select(Event)
                            .where(Event.event_type == "ARTIFACT_DISCOVERED")
                            .order_by(Event.sequence)
                        )
                    )
                    .scalars()
                    .all()
                )
                assert len(events) == 3
                assert events[0].artifact_ids_json == [specification.id]
                assert events[1].artifact_ids_json == [specification.id]
                assert all(event.artifact_ids_json for event in events)
        finally:
            await engine.dispose()

    asyncio.run(scenario())
