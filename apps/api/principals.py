from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.settings import Settings
from persistence.models import Principal


async def get_or_create_dev_principal(
    session: AsyncSession, settings: Settings
) -> Principal:
    principal = (
        await session.execute(
            select(Principal).where(Principal.id == settings.dev_principal_id)
        )
    ).scalar_one_or_none()
    if principal is not None:
        return principal

    principal = Principal(
        id=settings.dev_principal_id,
        auth_provider="development",
        auth_subject=settings.dev_principal_id,
        display_name=settings.dev_principal_display_name,
        email=settings.dev_principal_email,
    )
    session.add(principal)
    await session.flush()
    return principal
