from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api import idempotency
from api.dependencies import get_principal_id, get_session
from api.idempotency import IdempotencyConflictError
from api.principals import get_or_create_dev_principal
from api.problems import problem_response
from api.runs import owned_run
from domain.states import CommandState, EventSource, RunControlState
from domain.transitions import next_run_state
from persistence.events import append_event
from persistence.models import Command

router = APIRouter(tags=["commands"])


class StopRequest(BaseModel):
    mode: Literal["SAFE"] = "SAFE"


def command_response(command: Command) -> dict:
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
    return command_response(command)


@router.post("/runs/{run_id}/commands/stop", status_code=202)
async def request_safe_stop(
    run_id: str,
    payload: StopRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal_id: Annotated[str, Depends(get_principal_id)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    if idempotency_key is None:
        return problem_response(
            request,
            400,
            title="Bad Request",
            detail="Idempotency-Key header is required.",
            code="IDEMPOTENCY_KEY_REQUIRED",
        )
    run = await owned_run(session, principal_id, run_id)
    if run is None:
        return problem_response(
            request, 404, title="Not Found", detail="Run not found."
        )

    canonical_path = f"/api/v1/runs/{run_id}/commands/stop"
    body = payload.model_dump()
    hash_value = idempotency.request_hash(body)
    try:
        stored = await idempotency.replay(
            session,
            principal_id=principal_id,
            method="POST",
            canonical_path=canonical_path,
            idempotency_key=idempotency_key,
            request_hash_value=hash_value,
        )
    except IdempotencyConflictError:
        return problem_response(
            request,
            409,
            title="Conflict",
            detail="Idempotency-Key was reused with a different request.",
            code="IDEMPOTENCY_KEY_REUSED",
        )
    if stored is not None:
        return JSONResponse(status_code=stored.status, content=stored.snapshot or {})

    if run.control_state not in (
        RunControlState.RUNNING,
        RunControlState.WAITING_FOR_HUMAN,
    ):
        return problem_response(
            request,
            409,
            title="Conflict",
            detail="Run state does not allow a safe stop.",
            code="RUN_STATE_CONFLICT",
        )

    principal = await get_or_create_dev_principal(session, request.app.state.settings)
    moment = datetime.now(UTC)
    run.control_state = next_run_state(
        run.control_state, RunControlState.STOP_REQUESTED
    )
    run.version += 1
    run.updated_at = moment
    await append_event(
        session,
        run,
        event_type="RUN_STOP_REQUESTED",
        category="RUN",
        summary="Safe stop requested.",
        source=EventSource.CONTROL_PLANE,
    )
    command = Command(
        actor_principal_id=principal.id,
        command_type="SAFE_STOP_RUN",
        target_type="RUN",
        target_id=run.id,
        state=CommandState.ACCEPTED,
        request_json=body,
        request_hash=hash_value,
        idempotency_key=idempotency_key,
        request_id=getattr(request.state, "request_id", None),
    )
    session.add(command)
    await session.flush()
    response_body = command_response(command)
    await idempotency.store(
        session,
        principal_id=principal_id,
        method="POST",
        canonical_path=canonical_path,
        idempotency_key=idempotency_key,
        request_hash_value=hash_value,
        status=202,
        resource_ref=command.id,
        snapshot=response_body,
    )
    await session.commit()
    return JSONResponse(status_code=202, content=response_body)
