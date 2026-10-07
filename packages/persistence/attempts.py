from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.models import ExecutionAttempt, Run


async def create_attempt(session: AsyncSession, run: Run) -> ExecutionAttempt:
    max_ordinal = (
        await session.execute(
            select(func.max(ExecutionAttempt.ordinal)).where(
                ExecutionAttempt.run_id == run.id
            )
        )
    ).scalar()
    attempt = ExecutionAttempt(run_id=run.id, ordinal=(max_ordinal or 0) + 1)
    session.add(attempt)
    await session.flush()
    return attempt
