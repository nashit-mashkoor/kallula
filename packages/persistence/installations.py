from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.states import CompatibilityStatus, EngineInstallationStatus
from persistence.models import EngineInstallation


async def default_installation(session: AsyncSession) -> EngineInstallation | None:
    return (
        (
            await session.execute(
                select(EngineInstallation)
                .where(EngineInstallation.default_for_new_runs.is_(True))
                .order_by(EngineInstallation.created_at, EngineInstallation.id)
            )
        )
        .scalars()
        .first()
    )


def launch_compatible(installation: EngineInstallation) -> bool:
    return (
        installation.status is EngineInstallationStatus.SUPPORTED
        and installation.compatibility_launch is CompatibilityStatus.SUPPORTED
    )
