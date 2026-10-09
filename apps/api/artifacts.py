from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_principal_id, get_session
from api.problems import problem_response
from api.runs import owned_run
from persistence.models import Artifact, Project, Workspace
from runtime.base.storage import StorageError, resolve_under_root

router = APIRouter(tags=["artifacts"])


def artifact_response(artifact: Artifact) -> dict:
    return {
        "id": artifact.id,
        "project_id": artifact.project_id,
        "run_id": artifact.run_id,
        "attempt_id": artifact.attempt_id,
        "artifact_class": artifact.artifact_class.value,
        "display_name": artifact.display_name,
        "media_type": artifact.media_type,
        "size_bytes": artifact.size_bytes,
        "content_hash": artifact.content_hash,
        "storage_kind": artifact.storage_kind.value,
        "source_identity": artifact.source_identity_json,
        "metadata": artifact.metadata_json,
        "created_at": artifact.created_at.isoformat(),
    }


async def owned_artifact(
    session: AsyncSession, principal_id: str, artifact_id: str
) -> Artifact | None:
    return (
        await session.execute(
            select(Artifact)
            .join(Project, Artifact.project_id == Project.id)
            .where(Artifact.id == artifact_id, Project.owner_id == principal_id)
        )
    ).scalar_one_or_none()


@router.get("/runs/{run_id}/artifacts")
async def list_run_artifacts(
    run_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal_id: Annotated[str, Depends(get_principal_id)],
):
    run = await owned_run(session, principal_id, run_id)
    if run is None:
        return problem_response(
            request, 404, title="Not Found", detail="Run not found."
        )
    artifacts = (
        (
            await session.execute(
                select(Artifact)
                .where(Artifact.run_id == run_id)
                .order_by(Artifact.created_at, Artifact.id)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [artifact_response(artifact) for artifact in artifacts],
        "next_cursor": None,
    }


@router.get("/artifacts/{artifact_id}")
async def get_artifact(
    artifact_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal_id: Annotated[str, Depends(get_principal_id)],
):
    artifact = await owned_artifact(session, principal_id, artifact_id)
    if artifact is None:
        return problem_response(
            request, 404, title="Not Found", detail="Artifact not found."
        )
    return artifact_response(artifact)


@router.get("/artifacts/{artifact_id}/content")
async def get_artifact_content(
    artifact_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal_id: Annotated[str, Depends(get_principal_id)],
):
    artifact = await owned_artifact(session, principal_id, artifact_id)
    if artifact is None:
        return problem_response(
            request, 404, title="Not Found", detail="Artifact not found."
        )
    workspace = (
        await session.execute(
            select(Workspace).where(Workspace.project_id == artifact.project_id)
        )
    ).scalar_one_or_none()
    if workspace is None:
        return problem_response(
            request, 404, title="Not Found", detail="Artifact not found."
        )
    manager = request.app.state.workspace_manager
    try:
        workspace_path = manager.path_for(workspace.storage_key)
        path = resolve_under_root(workspace_path, artifact.storage_key)
    except StorageError:
        return problem_response(
            request, 404, title="Not Found", detail="Artifact not found."
        )
    if not path.is_file():
        return problem_response(
            request, 404, title="Not Found", detail="Artifact not found."
        )
    return FileResponse(
        path, media_type=artifact.media_type or "application/octet-stream"
    )
