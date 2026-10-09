import hashlib
import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api import idempotency
from api.dependencies import get_principal_id, get_session
from api.idempotency import IdempotencyConflictError
from api.installations import installation_response
from api.problems import problem_response
from api.projects import etag, owned_project
from domain.states import EventSource
from persistence import installations
from persistence.events import append_event
from persistence.models import EngineInstallation, Project, Run, RunConfigSnapshot

router = APIRouter(tags=["runs"])


class RunCreate(BaseModel):
    objective: str
    agent_profile_version_id: str | None = None
    environment_profile_version_id: str | None = None


def content_hash(values: dict) -> str:
    encoded = json.dumps(values, sort_keys=True, default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def run_response(run: Run) -> dict:
    stage: dict | None = None
    if run.current_stage_category is not None:
        stage = {
            "category": run.current_stage_category,
            "native_id": run.current_stage_native_id,
            "display_label": run.current_stage_label,
            "order": run.current_stage_order,
        }
    failure: dict | None = None
    if run.failure_class is not None or run.failure_code is not None:
        failure = {
            "class": run.failure_class,
            "code": run.failure_code,
            "summary": run.failure_summary,
            "recoverability": run.recoverability.value if run.recoverability else None,
            "evidence_artifact_ids": [],
        }
    return {
        "id": run.id,
        "project_id": run.project_id,
        "ordinal": run.ordinal,
        "objective": run.objective,
        "control_state": run.control_state.value,
        "stage": stage,
        "active_work_item_id": run.active_work_item_id,
        "effective_config_snapshot_id": run.effective_config_snapshot_id,
        "engine_installation_id": run.engine_installation_id,
        "environment_snapshot_id": run.environment_snapshot_id,
        "active_attempt_id": run.active_attempt_id,
        "pending_interaction_id": run.pending_interaction_id,
        "last_event_sequence": run.last_event_sequence,
        "last_verified_state_id": run.last_verified_state_id,
        "recovery": {"resume_allowed": False, "reason": None},
        "failure": failure,
        "created_at": run.created_at.isoformat(),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "updated_at": run.updated_at.isoformat(),
        "version": run.version,
    }


def config_response(
    snapshot: RunConfigSnapshot, installation: EngineInstallation | None
) -> dict:
    return {
        "id": snapshot.id,
        "run_id": snapshot.run_id,
        "engine_installation_id": snapshot.engine_installation_id,
        "engine_installation": (
            installation_response(installation) if installation else None
        ),
        "capability_manifest_hash": snapshot.capability_manifest_hash,
        "agent_profile_version_id": snapshot.agent_profile_version_id,
        "agent_slots": snapshot.agent_slots_json,
        "provider_model_assignments": snapshot.provider_model_assignments_json,
        "reasoning_tool_settings": snapshot.reasoning_tool_settings_json,
        "engineering_preferences": snapshot.engineering_preferences_json,
        "skill_identities": snapshot.skill_identities_json,
        "environment_profile_version_id": snapshot.environment_profile_version_id,
        "permitted_credential_refs": snapshot.permitted_credential_refs_json,
        "starting_git_commit": snapshot.starting_git_commit,
        "starting_git_dirty": snapshot.starting_git_dirty,
        "starting_git_status_hash": snapshot.starting_git_status_hash,
        "created_at": snapshot.created_at.isoformat(),
        "content_hash": snapshot.content_hash,
    }


async def owned_run(
    session: AsyncSession, principal_id: str, run_id: str
) -> Run | None:
    return (
        await session.execute(
            select(Run)
            .join(Project, Run.project_id == Project.id)
            .where(Run.id == run_id, Project.owner_id == principal_id)
        )
    ).scalar_one_or_none()


async def owned_snapshot(
    session: AsyncSession, principal_id: str, run_id: str
) -> RunConfigSnapshot | None:
    return (
        await session.execute(
            select(RunConfigSnapshot)
            .join(Run, RunConfigSnapshot.run_id == Run.id)
            .join(Project, Run.project_id == Project.id)
            .where(Run.id == run_id, Project.owner_id == principal_id)
        )
    ).scalar_one_or_none()


@router.get("/projects/{project_id}/runs")
async def list_runs(
    project_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal_id: Annotated[str, Depends(get_principal_id)],
):
    project = await owned_project(session, principal_id, project_id)
    if project is None:
        return problem_response(
            request, 404, title="Not Found", detail="Project not found."
        )
    runs = (
        (
            await session.execute(
                select(Run)
                .where(Run.project_id == project.id)
                .order_by(Run.ordinal.desc())
            )
        )
        .scalars()
        .all()
    )
    return {"items": [run_response(run) for run in runs], "next_cursor": None}


@router.post("/projects/{project_id}/runs", status_code=201)
async def create_run(
    project_id: str,
    payload: RunCreate,
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

    project = await owned_project(session, principal_id, project_id)
    if project is None:
        return problem_response(
            request, 404, title="Not Found", detail="Project not found."
        )

    canonical_path = f"/api/v1/projects/{project_id}/runs"
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
        snapshot_response = stored.snapshot or {}
        return JSONResponse(
            status_code=stored.status,
            content=snapshot_response,
            headers={"ETag": etag(snapshot_response.get("version", 1))},
        )

    installation = await installations.default_installation(session)
    if installation is None or not installations.launch_compatible(installation):
        return problem_response(
            request,
            409,
            title="Conflict",
            detail="No launch-compatible engine installation is available.",
            code="ENGINE_INCOMPATIBLE",
        )

    max_ordinal = (
        await session.execute(
            select(func.max(Run.ordinal)).where(Run.project_id == project.id)
        )
    ).scalar()
    run = Run(
        project_id=project.id,
        ordinal=(max_ordinal or 0) + 1,
        objective=payload.objective,
        engine_installation_id=installation.id,
    )
    session.add(run)
    await session.flush()

    await append_event(
        session,
        run,
        event_type="RUN_QUEUED",
        category="RUN",
        summary="Run queued.",
        source=EventSource.CONTROL_PLANE,
    )

    snapshot = RunConfigSnapshot(
        run_id=run.id,
        engine_installation_id=installation.id,
        capability_manifest_hash=content_hash(installation.capability_manifest_json),
        agent_profile_version_id=payload.agent_profile_version_id,
        environment_profile_version_id=payload.environment_profile_version_id,
        content_hash=content_hash({**body, "engine_installation_id": installation.id}),
    )
    session.add(snapshot)
    await session.flush()
    run.effective_config_snapshot_id = snapshot.id
    project.current_run_id = run.id
    await session.flush()

    response_body = run_response(run)
    await idempotency.store(
        session,
        principal_id=principal_id,
        method="POST",
        canonical_path=canonical_path,
        idempotency_key=idempotency_key,
        request_hash_value=hash_value,
        status=201,
        resource_ref=run.id,
        snapshot=response_body,
    )
    await session.commit()
    return JSONResponse(
        status_code=201, content=response_body, headers={"ETag": etag(run.version)}
    )


@router.get("/runs/{run_id}")
async def get_run(
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
    return JSONResponse(content=run_response(run), headers={"ETag": etag(run.version)})


@router.get("/runs/{run_id}/configuration")
async def get_run_configuration(
    run_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal_id: Annotated[str, Depends(get_principal_id)],
):
    snapshot = await owned_snapshot(session, principal_id, run_id)
    if snapshot is None:
        return problem_response(
            request, 404, title="Not Found", detail="Run not found."
        )
    installation = None
    if snapshot.engine_installation_id is not None:
        installation = (
            await session.execute(
                select(EngineInstallation).where(
                    EngineInstallation.id == snapshot.engine_installation_id
                )
            )
        ).scalar_one_or_none()
    return config_response(snapshot, installation)
