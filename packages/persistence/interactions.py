from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.states import InteractionState
from persistence.models import InteractionResponse, PendingInteraction


async def open_for_run(session: AsyncSession, run_id: str) -> PendingInteraction | None:
    """The single OPEN interaction of a Run, if one exists."""
    return (
        await session.execute(
            select(PendingInteraction).where(
                PendingInteraction.run_id == run_id,
                PendingInteraction.status == InteractionState.OPEN,
            )
        )
    ).scalar_one_or_none()


async def latest_response_for_run(
    session: AsyncSession, run_id: str
) -> tuple[InteractionResponse, PendingInteraction] | None:
    """The most recent accepted response of a Run, with its interaction."""
    row = (
        await session.execute(
            select(InteractionResponse, PendingInteraction)
            .join(
                PendingInteraction,
                InteractionResponse.interaction_id == PendingInteraction.id,
            )
            .where(InteractionResponse.run_id == run_id)
            .order_by(
                PendingInteraction.created_at.desc(), PendingInteraction.id.desc()
            )
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    return row[0], row[1]
