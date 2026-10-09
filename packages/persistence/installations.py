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


async def find_by_identity(
    session: AsyncSession,
    *,
    engine_family: str,
    engine_revision: str,
    adapter_version: str,
) -> EngineInstallation | None:
    return (
        await session.execute(
            select(EngineInstallation).where(
                EngineInstallation.engine_family == engine_family,
                EngineInstallation.engine_revision == engine_revision,
                EngineInstallation.adapter_version == adapter_version,
            )
        )
    ).scalar_one_or_none()


async def register(
    session: AsyncSession,
    *,
    engine_family: str,
    engine_revision: str,
    adapter_version: str,
    installation_digest: str,
    capability_manifest: dict,
    status: EngineInstallationStatus = EngineInstallationStatus.SUPPORTED,
    default_for_new_runs: bool = True,
    compatibility_launch: CompatibilityStatus = CompatibilityStatus.SUPPORTED,
) -> EngineInstallation:
    existing = await find_by_identity(
        session,
        engine_family=engine_family,
        engine_revision=engine_revision,
        adapter_version=adapter_version,
    )
    if existing is not None:
        return existing
    if default_for_new_runs:
        current_defaults = (
            (
                await session.execute(
                    select(EngineInstallation).where(
                        EngineInstallation.default_for_new_runs.is_(True)
                    )
                )
            )
            .scalars()
            .all()
        )
        for other in current_defaults:
            other.default_for_new_runs = False
    installation = EngineInstallation(
        engine_family=engine_family,
        engine_revision=engine_revision,
        adapter_version=adapter_version,
        installation_digest=installation_digest,
        status=status,
        default_for_new_runs=default_for_new_runs,
        compatibility_launch=compatibility_launch,
        capability_manifest_json=capability_manifest,
    )
    session.add(installation)
    await session.flush()
    return installation
