from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.states import WorkItemState
from persistence.models import Run, WorkItem


def engine_key(native_id: str) -> str:
    return f"issue:{native_id}"


def title_for(native_id: str, title: str | None) -> str:
    return title or f"Issue #{native_id}"


async def get_by_engine_key(
    session: AsyncSession, run_id: str, key: str
) -> WorkItem | None:
    return (
        await session.execute(
            select(WorkItem).where(
                WorkItem.run_id == run_id, WorkItem.engine_key == key
            )
        )
    ).scalar_one_or_none()


async def _get_or_create(
    session: AsyncSession, run: Run, native_id: str, title: str | None
) -> WorkItem:
    key = engine_key(native_id)
    item = await get_by_engine_key(session, run.id, key)
    if item is not None:
        if title and item.title != title:
            item.title = title
        return item
    ordinal = int(native_id) if native_id.isdigit() else None
    item = WorkItem(
        run_id=run.id,
        engine_key=key,
        ordinal=ordinal,
        title=title_for(native_id, title),
    )
    session.add(item)
    await session.flush()
    return item


def _touch(item: WorkItem) -> None:
    item.updated_at = datetime.now(UTC)
    item.version += 1


async def record_discovered(
    session: AsyncSession, run: Run, native_id: str, title: str | None
) -> WorkItem:
    return await _get_or_create(session, run, native_id, title)


async def record_started(
    session: AsyncSession, run: Run, native_id: str, title: str | None
) -> WorkItem:
    item = await _get_or_create(session, run, native_id, title)
    item.state = WorkItemState.ACTIVE
    item.attempt_count += 1
    _touch(item)
    return item


async def record_completed(
    session: AsyncSession, run: Run, native_id: str, title: str | None
) -> WorkItem:
    item = await _get_or_create(session, run, native_id, title)
    item.state = WorkItemState.COMPLETED
    item.blocker = None
    _touch(item)
    return item


async def record_blocked(
    session: AsyncSession,
    run: Run,
    native_id: str,
    title: str | None,
    blocker: str | None,
) -> WorkItem:
    item = await _get_or_create(session, run, native_id, title)
    item.state = WorkItemState.BLOCKED
    item.blocker = blocker
    _touch(item)
    return item


async def record_skipped(
    session: AsyncSession,
    run: Run,
    native_id: str,
    title: str | None,
    blocker: str | None,
) -> WorkItem:
    item = await _get_or_create(session, run, native_id, title)
    item.state = WorkItemState.SKIPPED
    item.blocker = blocker
    _touch(item)
    return item
