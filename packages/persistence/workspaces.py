from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.models import Workspace


async def get_for_project(session: AsyncSession, project_id: str) -> Workspace | None:
    return (
        await session.execute(
            select(Workspace).where(Workspace.project_id == project_id)
        )
    ).scalar_one_or_none()
