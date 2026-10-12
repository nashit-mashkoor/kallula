from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_principal_id, get_session
from api.problems import problem_response
from api.runs import owned_run
from persistence.models import ExecutionAttempt

router = APIRouter(tags=["attempts"])


def attempt_response(attempt: ExecutionAttempt) -> dict:
    observed_checkpoint = None
    if attempt.observed_stage_category is not None:
        observed_checkpoint = {
            "stage_category": attempt.observed_stage_category,
            "opaque_engine_state_ref": attempt.observed_engine_state_ref,
        }
    return {
        "id": attempt.id,
        "run_id": attempt.run_id,
        "ordinal": attempt.ordinal,
        "state": attempt.state.value,
        "engine_installation_id": attempt.engine_installation_id,
        "environment_snapshot_id": attempt.environment_snapshot_id,
        "created_at": attempt.created_at.isoformat(),
        "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
        "ended_at": attempt.ended_at.isoformat() if attempt.ended_at else None,
        "last_heartbeat_at": (
            attempt.last_heartbeat_at.isoformat() if attempt.last_heartbeat_at else None
        ),
        "terminal_reason": attempt.terminal_reason,
        "observed_checkpoint": observed_checkpoint,
        "log_stream_id": attempt.log_stream_id,
    }


@router.get("/runs/{run_id}/attempts")
async def list_run_attempts(
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
    attempts = (
        (
            await session.execute(
                select(ExecutionAttempt)
                .where(ExecutionAttempt.run_id == run_id)
                .order_by(ExecutionAttempt.ordinal)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [attempt_response(attempt) for attempt in attempts],
        "next_cursor": None,
    }
