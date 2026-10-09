from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.states import ArtifactClass, ArtifactStorageKind
from persistence.models import Artifact, Run


async def get_by_storage_key(
    session: AsyncSession, run_id: str, storage_key: str
) -> Artifact | None:
    return (
        await session.execute(
            select(Artifact).where(
                Artifact.run_id == run_id, Artifact.storage_key == storage_key
            )
        )
    ).scalar_one_or_none()


def _artifact_class(value: object) -> ArtifactClass:
    try:
        return ArtifactClass(str(value))
    except ValueError:
        return ArtifactClass.OTHER


async def store_from_event(
    session: AsyncSession,
    run: Run,
    attempt_id: str | None,
    payload: dict,
) -> Artifact:
    storage_key = str(payload.get("relative_path", ""))
    existing = await get_by_storage_key(session, run.id, storage_key)
    if existing is not None:
        return existing
    artifact = Artifact(
        project_id=run.project_id,
        run_id=run.id,
        attempt_id=attempt_id,
        artifact_class=_artifact_class(payload.get("artifact_class")),
        display_name=str(payload.get("display_name") or "Artifact"),
        media_type=payload.get("media_type"),
        size_bytes=payload.get("size_bytes"),
        content_hash=payload.get("content_hash"),
        storage_kind=ArtifactStorageKind.WORKSPACE_REFERENCE,
        storage_key=storage_key,
        source_identity_json=payload.get("source_identity") or {},
    )
    session.add(artifact)
    await session.flush()
    return artifact
