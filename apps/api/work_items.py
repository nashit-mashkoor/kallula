from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_principal_id, get_session
from api.problems import problem_response
from api.runs import owned_run
from persistence.models import Project, Run, WorkItem

router = APIRouter(tags=["work-items"])


def work_item_response(item: WorkItem) -> dict:
    return {
        "id": item.id,
        "run_id": item.run_id,
        "engine_key": item.engine_key,
        "ordinal": item.ordinal,
        "title": item.title,
        "description": item.description,
        "acceptance_criteria": item.acceptance_criteria_json,
        "state": item.state.value,
        "blocker": item.blocker,
        "related_commit": item.related_commit,
        "attempt_count": item.attempt_count,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "version": item.version,
    }


async def owned_work_item(
    session: AsyncSession, principal_id: str, work_item_id: str
) -> WorkItem | None:
    return (
        await session.execute(
            select(WorkItem)
            .join(Run, WorkItem.run_id == Run.id)
            .join(Project, Run.project_id == Project.id)
            .where(WorkItem.id == work_item_id, Project.owner_id == principal_id)
        )
    ).scalar_one_or_none()


@router.get("/runs/{run_id}/work-items")
async def list_run_work_items(
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
    items = (
        (
            await session.execute(
                select(WorkItem)
                .where(WorkItem.run_id == run_id)
                .order_by(WorkItem.ordinal, WorkItem.engine_key)
            )
        )
        .scalars()
        .all()
    )
    return {"items": [work_item_response(item) for item in items], "next_cursor": None}


@router.get("/work-items/{work_item_id}")
async def get_work_item(
    work_item_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal_id: Annotated[str, Depends(get_principal_id)],
):
    item = await owned_work_item(session, principal_id, work_item_id)
    if item is None:
        return problem_response(
            request, 404, title="Not Found", detail="Work item not found."
        )
    return work_item_response(item)
