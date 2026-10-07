from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.models import ProjectExecutionLease

LEASE_DURATION = timedelta(minutes=1)


class LeaseConflictError(RuntimeError):
    pass


def _naive_utc(value: datetime | None = None) -> datetime:
    moment = value or datetime.now(UTC)
    return moment.replace(tzinfo=None)


async def _lease(
    session: AsyncSession, project_id: str
) -> ProjectExecutionLease | None:
    return (
        await session.execute(
            select(ProjectExecutionLease).where(
                ProjectExecutionLease.project_id == project_id
            )
        )
    ).scalar_one_or_none()


async def acquire(
    session: AsyncSession,
    *,
    project_id: str,
    holder_id: str,
    run_id: str | None = None,
    attempt_id: str | None = None,
    now: datetime | None = None,
    duration: timedelta = LEASE_DURATION,
) -> ProjectExecutionLease:
    moment = _naive_utc(now)
    lease = await _lease(session, project_id)
    if lease is not None and lease.expires_at > moment:
        raise LeaseConflictError(project_id)

    if lease is None:
        lease = ProjectExecutionLease(
            project_id=project_id,
            run_id=run_id,
            attempt_id=attempt_id,
            holder_id=holder_id,
            acquired_at=moment,
            renewed_at=moment,
            expires_at=moment + duration,
            lease_epoch=1,
        )
        session.add(lease)
    else:
        lease.run_id = run_id
        lease.attempt_id = attempt_id
        lease.holder_id = holder_id
        lease.acquired_at = moment
        lease.renewed_at = moment
        lease.expires_at = moment + duration
        lease.lease_epoch += 1
    await session.flush()
    return lease


async def renew(
    session: AsyncSession,
    *,
    project_id: str,
    holder_id: str,
    lease_epoch: int,
    now: datetime | None = None,
    duration: timedelta = LEASE_DURATION,
) -> ProjectExecutionLease:
    moment = _naive_utc(now)
    lease = await _lease(session, project_id)
    if (
        lease is None
        or lease.holder_id != holder_id
        or lease.lease_epoch != lease_epoch
    ):
        raise LeaseConflictError(project_id)
    if lease.expires_at <= moment:
        raise LeaseConflictError(project_id)

    lease.renewed_at = moment
    lease.expires_at = moment + duration
    await session.flush()
    return lease


async def release(
    session: AsyncSession, *, project_id: str, holder_id: str, lease_epoch: int
) -> None:
    lease = await _lease(session, project_id)
    if (
        lease is None
        or lease.holder_id != holder_id
        or lease.lease_epoch != lease_epoch
    ):
        raise LeaseConflictError(project_id)
    await session.delete(lease)
    await session.flush()


async def clear_expired(
    session: AsyncSession, *, project_id: str, now: datetime | None = None
) -> bool:
    moment = _naive_utc(now)
    lease = await _lease(session, project_id)
    if lease is None or lease.expires_at > moment:
        return False
    await session.delete(lease)
    await session.flush()
    return True
