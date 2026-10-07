from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_session
from api.problems import problem_response
from persistence.models import Command

router = APIRouter(tags=["commands"])


@router.get("/commands/{command_id}")
async def get_command(
    command_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    command = (
        await session.execute(select(Command).where(Command.id == command_id))
    ).scalar_one_or_none()
    if command is None:
        return problem_response(
            request, 404, title="Not Found", detail="Command not found."
        )
    return {
        "id": command.id,
        "command_type": command.command_type,
        "target_type": command.target_type,
        "target_id": command.target_id,
        "state": command.state.value,
        "actor_principal_id": command.actor_principal_id,
        "created_at": command.created_at.isoformat(),
        "processing_at": command.processing_at.isoformat()
        if command.processing_at
        else None,
        "applied_at": command.applied_at.isoformat() if command.applied_at else None,
        "failed_at": command.failed_at.isoformat() if command.failed_at else None,
        "failure": (
            {"code": command.failure_code, "summary": command.failure_summary}
            if command.failure_code or command.failure_summary
            else None
        ),
        "result_refs": command.result_refs_json,
    }
