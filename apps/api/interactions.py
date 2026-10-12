from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api import idempotency
from api.commands import command_response
from api.dependencies import get_principal_id, get_session
from api.idempotency import IdempotencyConflictError
from api.principals import get_or_create_dev_principal
from api.problems import problem_response
from domain.states import (
    CommandState,
    EventSource,
    InteractionKind,
    InteractionResponseType,
    InteractionState,
    RunControlState,
)
from domain.transitions import next_run_state
from persistence.events import append_event
from persistence.models import (
    Command,
    InteractionResponse,
    PendingInteraction,
    Project,
    Run,
)

router = APIRouter(tags=["interactions"])

QUESTION_RESPONSES = ("ANSWER", "USE_RECOMMENDATION", "DELEGATE_REMAINING")
CONFIRMATION_RESPONSES = ("CONFIRM", "REQUEST_CHANGE")
TITLES = {
    InteractionKind.QUESTION: "Requirements question",
    InteractionKind.FINAL_INTENT_CONFIRMATION: "Final intent confirmation",
}


class RespondRequest(BaseModel):
    response_type: Literal[
        "ANSWER",
        "USE_RECOMMENDATION",
        "CONFIRM",
        "REQUEST_CHANGE",
        "DELEGATE_REMAINING",
    ]
    answer: str | None = None


def allowed_responses(kind: InteractionKind) -> list[str]:
    if kind is InteractionKind.FINAL_INTENT_CONFIRMATION:
        return list(CONFIRMATION_RESPONSES)
    return list(QUESTION_RESPONSES)


def answer_for(
    response_type: InteractionResponseType,
    interaction: PendingInteraction,
    answer: str,
) -> str | None:
    """The self-contained answer the coordinator delivers to the engine."""
    if response_type is InteractionResponseType.USE_RECOMMENDATION:
        return interaction.recommendation
    return answer or None


def interaction_response(interaction: PendingInteraction) -> dict:
    return {
        "id": interaction.id,
        "run_id": interaction.run_id,
        "attempt_id": interaction.attempt_id,
        "kind": interaction.kind.value,
        "status": interaction.status.value,
        "title": interaction.title,
        "prompt": interaction.prompt,
        "recommendation": interaction.recommendation,
        "context": interaction.context_json,
        "allowed_responses": interaction.allowed_responses_json,
        "created_at": interaction.created_at.isoformat(),
        "resolved_at": interaction.resolved_at.isoformat()
        if interaction.resolved_at
        else None,
        "version": interaction.version,
    }


async def owned_interaction(
    session: AsyncSession, principal_id: str, interaction_id: str
) -> PendingInteraction | None:
    return (
        await session.execute(
            select(PendingInteraction)
            .join(Run, PendingInteraction.run_id == Run.id)
            .join(Project, Run.project_id == Project.id)
            .where(
                PendingInteraction.id == interaction_id,
                Project.owner_id == principal_id,
            )
        )
    ).scalar_one_or_none()


@router.get("/interactions")
async def list_interactions(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal_id: Annotated[str, Depends(get_principal_id)],
    status: Annotated[str, Query()] = "OPEN",
):
    try:
        wanted = [InteractionState(status)]
    except ValueError:
        return problem_response(
            request,
            422,
            title="Validation Error",
            detail="Unknown interaction status filter.",
            code="VALIDATION_ERROR",
        )
    interactions = (
        (
            await session.execute(
                select(PendingInteraction)
                .join(Run, PendingInteraction.run_id == Run.id)
                .join(Project, Run.project_id == Project.id)
                .where(
                    Project.owner_id == principal_id,
                    PendingInteraction.status.in_(wanted),
                )
                .order_by(PendingInteraction.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [interaction_response(item) for item in interactions],
        "next_cursor": None,
    }


@router.get("/interactions/{interaction_id}")
async def get_interaction(
    interaction_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal_id: Annotated[str, Depends(get_principal_id)],
):
    interaction = await owned_interaction(session, principal_id, interaction_id)
    if interaction is None:
        return problem_response(
            request, 404, title="Not Found", detail="Interaction not found."
        )
    return interaction_response(interaction)


@router.post("/interactions/{interaction_id}/commands/respond", status_code=202)
async def respond_to_interaction(
    interaction_id: str,
    payload: RespondRequest,
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
    interaction = await owned_interaction(session, principal_id, interaction_id)
    if interaction is None:
        return problem_response(
            request, 404, title="Not Found", detail="Interaction not found."
        )

    canonical_path = f"/api/v1/interactions/{interaction_id}/commands/respond"
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

    if interaction.status is not InteractionState.OPEN:
        return problem_response(
            request,
            409,
            title="Conflict",
            detail="The interaction was already resolved.",
            code="INTERACTION_ALREADY_RESOLVED",
        )

    allowed = allowed_responses(interaction.kind)
    if payload.response_type not in allowed:
        return problem_response(
            request,
            422,
            title="Validation Error",
            detail="The response type is not allowed for this interaction.",
            code="VALIDATION_ERROR",
        )
    answer = (payload.answer or "").strip()
    if payload.response_type in ("ANSWER", "REQUEST_CHANGE") and not answer:
        return problem_response(
            request,
            422,
            title="Validation Error",
            detail="This response type requires an answer.",
            code="VALIDATION_ERROR",
        )

    run = (
        await session.execute(select(Run).where(Run.id == interaction.run_id))
    ).scalar_one()
    if run.control_state is not RunControlState.WAITING_FOR_HUMAN:
        return problem_response(
            request,
            409,
            title="Conflict",
            detail="The Run is not waiting for human input.",
            code="RUN_STATE_CONFLICT",
        )

    principal = await get_or_create_dev_principal(session, request.app.state.settings)
    moment = datetime.now(UTC)
    response_type = InteractionResponseType(payload.response_type)
    interaction.status = (
        InteractionState.DELEGATED
        if response_type is InteractionResponseType.DELEGATE_REMAINING
        else InteractionState.ANSWERED
    )
    interaction.resolved_at = moment
    interaction.version += 1

    if run.pending_interaction_id == interaction.id:
        run.pending_interaction_id = None
    run.control_state = next_run_state(run.control_state, RunControlState.QUEUED)
    run.version += 1
    run.updated_at = moment

    command = Command(
        actor_principal_id=principal.id,
        command_type="RESPOND_INTERACTION",
        target_type="INTERACTION",
        target_id=interaction.id,
        state=CommandState.APPLIED,
        request_json=body,
        request_hash=hash_value,
        idempotency_key=idempotency_key,
        applied_at=moment,
        request_id=getattr(request.state, "request_id", None),
    )
    session.add(command)
    await session.flush()
    response = InteractionResponse(
        interaction_id=interaction.id,
        run_id=run.id,
        actor_principal_id=principal.id,
        response_type=response_type,
        answer_text=answer_for(response_type, interaction, answer),
        command_id=command.id,
    )
    session.add(response)
    await session.flush()
    command.result_refs_json = {"interaction_response_id": response.id}
    await append_event(
        session,
        run,
        event_type="INTERACTION_RESOLVED",
        category="INTERACTION",
        summary="Human response accepted.",
        source=EventSource.CONTROL_PLANE,
        payload={
            "interaction_id": interaction.id,
            "response_type": response_type.value,
        },
    )
    await append_event(
        session,
        run,
        event_type="RUN_QUEUED",
        category="RUN",
        summary="Run queued to continue after the human response.",
        source=EventSource.CONTROL_PLANE,
    )
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
