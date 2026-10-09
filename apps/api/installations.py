from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_principal_id, get_session
from api.problems import problem_response
from persistence.models import EngineInstallation

router = APIRouter(tags=["engine-installations"])


def installation_response(installation: EngineInstallation) -> dict:
    return {
        "id": installation.id,
        "engine_family": installation.engine_family,
        "engine_revision": installation.engine_revision,
        "adapter_version": installation.adapter_version,
        "installation_digest": installation.installation_digest,
        "status": installation.status.value,
        "default_for_new_runs": installation.default_for_new_runs,
        "compatibility": {
            "launch": installation.compatibility_launch.value,
            "state_format": installation.compatibility_state_format.value,
            "resume": installation.compatibility_resume.value,
            "security": installation.compatibility_security.value,
            "runtime": installation.compatibility_runtime.value,
        },
        "capability_manifest": installation.capability_manifest_json,
        "created_at": installation.created_at.isoformat(),
    }


@router.get("/engine-installations")
async def list_engine_installations(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal_id: Annotated[str, Depends(get_principal_id)],
):
    installations = (
        (
            await session.execute(
                select(EngineInstallation).order_by(
                    EngineInstallation.created_at, EngineInstallation.id
                )
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [installation_response(item) for item in installations],
        "next_cursor": None,
    }


@router.get("/engine-installations/{engine_installation_id}")
async def get_engine_installation(
    engine_installation_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal_id: Annotated[str, Depends(get_principal_id)],
):
    installation = (
        await session.execute(
            select(EngineInstallation).where(
                EngineInstallation.id == engine_installation_id
            )
        )
    ).scalar_one_or_none()
    if installation is None:
        return problem_response(
            request,
            404,
            title="Not Found",
            detail="Engine installation not found.",
        )
    return installation_response(installation)
