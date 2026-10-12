import logging

from sqlalchemy.ext.asyncio import AsyncSession

from coordinator.active import ActiveRuns
from persistence import leases

logger = logging.getLogger("coordinator")

LEASE_RENEW_INTERVAL_SECONDS = 20.0


async def renew_active_leases(session: AsyncSession, active: ActiveRuns) -> int:
    renewed = 0
    for run_id, entry in active.items():
        if entry.project_id is None or entry.lease_epoch is None:
            continue
        try:
            await leases.renew(
                session,
                project_id=entry.project_id,
                holder_id=entry.holder_id or "",
                lease_epoch=entry.lease_epoch,
            )
        except leases.LeaseConflictError:
            logger.warning(
                "lease lost; requesting safe stop",
                extra={"run_id": run_id},
            )
            entry.signal.set()
            await session.rollback()
            continue
        renewed += 1
    if renewed:
        await session.commit()
    return renewed
