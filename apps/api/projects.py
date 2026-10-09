from datetime import UTC, datetime
from typing import Annotated

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
from persistence.models import OriginType, Project, Workspace, WorkspaceStatus
from runtime.base.workspace import WorkspaceError, WorkspaceManager

router = APIRouter(tags=["projects"])

CANONICAL_PATH = "/api/v1/projects"


class Origin(BaseModel):
    type: str = "NEW_IDEA"
    idea: str | None = None
    repository: dict | None = None


class ProjectCreate(BaseModel):
    display_name: str
    origin: Origin | None = None


class ProjectPatch(BaseModel):
    display_name: str | None = None
    default_agent_profile_version_id: str | None = None
    default_environment_profile_version_id: str | None = None
    engineering_preferences: dict | None = None


def etag(version: int) -> str:
    return f'"v{version}"'


def project_response(project: Project) -> dict:
    return {
        "id": project.id,
        "display_name": project.display_name,
        "owner_id": project.owner_id,
        "origin": {
            "type": project.origin_type.value,
            "repository": project.origin_metadata_json.get("repository"),
        },
        "workspace_status": project.workspace_status.value,
        "workspace_error": project.workspace_error_code,
        "default_engine_policy": project.default_engine_policy_json,
        "default_agent_profile_version_id": project.default_agent_profile_version_id,
        "default_environment_profile_version_id": project.default_environment_profile_version_id,
        "engineering_preferences": project.engineering_preferences_json,
        "current_verified_state_id": project.current_verified_state_id,
        "current_run_id": project.current_run_id,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
        "version": project.version,
    }


async def owned_project(
    session: AsyncSession, principal_id: str, project_id: str
) -> Project | None:
    return (
        await session.execute(
            select(Project).where(
                Project.id == project_id, Project.owner_id == principal_id
            )
        )
    ).scalar_one_or_none()


@router.get("/projects")
async def list_projects(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal_id: Annotated[str, Depends(get_principal_id)],
):
    projects = (
        (
            await session.execute(
                select(Project)
                .where(Project.owner_id == principal_id)
                .order_by(Project.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [project_response(project) for project in projects],
        "next_cursor": None,
    }


@router.post("/projects", status_code=201)
async def create_project(
    payload: ProjectCreate,
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

    try:
        origin_type = (
            OriginType(payload.origin.type) if payload.origin else OriginType.NEW_IDEA
        )
    except ValueError:
        return problem_response(
            request,
            400,
            title="Bad Request",
            detail="Unknown origin type.",
            code="INVALID_ORIGIN_TYPE",
        )

    body = payload.model_dump()
    hash_value = idempotency.request_hash(body)
    try:
        stored = await idempotency.replay(
            session,
            principal_id=principal_id,
            method="POST",
            canonical_path=CANONICAL_PATH,
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
        snapshot = stored.snapshot or {}
        return JSONResponse(
            status_code=stored.status,
            content=snapshot,
            headers={"ETag": etag(snapshot.get("version", 1))},
        )

    principal = await get_or_create_dev_principal(session, request.app.state.settings)
    project = Project(
        owner_id=principal.id,
        display_name=payload.display_name,
        origin_type=origin_type,
        origin_metadata_json=body.get("origin") or {},
    )
    session.add(project)
    await session.flush()

    workspace = Workspace(
        project_id=project.id,
        storage_driver="local",
        storage_key=f"projects/{project.id}/workspace",
    )
    session.add(workspace)
    await session.flush()

    manager: WorkspaceManager = request.app.state.workspace_manager
    try:
        manager.allocate(workspace.storage_key)
    except WorkspaceError as exc:
        await session.rollback()
        internal = exc.code == "WORKSPACE_PATH_ESCAPE"
        return problem_response(
            request,
            500 if internal else 503,
            detail="The project workspace could not be allocated.",
            code="INTERNAL_ERROR" if internal else "DEPENDENCY_UNAVAILABLE",
        )

    workspace.status = WorkspaceStatus.READY
    workspace.validated_at = datetime.now(UTC)
    project.workspace_id = workspace.id
    project.workspace_status = WorkspaceStatus.READY
    await session.flush()

    response_body = project_response(project)
    await idempotency.store(
        session,
        principal_id=principal_id,
        method="POST",
        canonical_path=CANONICAL_PATH,
        idempotency_key=idempotency_key,
        request_hash_value=hash_value,
        status=201,
        resource_ref=project.id,
        snapshot=response_body,
    )
    await session.commit()
    return JSONResponse(
        status_code=201, content=response_body, headers={"ETag": etag(project.version)}
    )


@router.get("/projects/{project_id}")
async def get_project(
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
    return JSONResponse(
        content=project_response(project), headers={"ETag": etag(project.version)}
    )


@router.patch("/projects/{project_id}")
async def patch_project(
    project_id: str,
    payload: ProjectPatch,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal_id: Annotated[str, Depends(get_principal_id)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
):
    project = await owned_project(session, principal_id, project_id)
    if project is None:
        return problem_response(
            request, 404, title="Not Found", detail="Project not found."
        )

    if if_match is None:
        return problem_response(
            request,
            428,
            title="Precondition Required",
            detail="If-Match header is required.",
            code="PRECONDITION_REQUIRED",
        )
    if if_match.strip('"') != f"v{project.version}":
        return problem_response(
            request,
            412,
            title="Precondition Failed",
            detail="The resource version does not match.",
            code="PRECONDITION_FAILED",
        )

    if payload.display_name is not None:
        project.display_name = payload.display_name
    if payload.default_agent_profile_version_id is not None:
        project.default_agent_profile_version_id = (
            payload.default_agent_profile_version_id
        )
    if payload.default_environment_profile_version_id is not None:
        project.default_environment_profile_version_id = (
            payload.default_environment_profile_version_id
        )
    if payload.engineering_preferences is not None:
        project.engineering_preferences_json = payload.engineering_preferences

    project.version += 1
    project.updated_at = datetime.now(UTC)
    await session.commit()
    return JSONResponse(
        content=project_response(project), headers={"ETag": etag(project.version)}
    )
