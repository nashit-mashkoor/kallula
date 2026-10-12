from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coordinator.active import ActiveRuns
from domain.states import CommandState
from persistence.models import Command

SAFE_STOP_COMMAND = "SAFE_STOP_RUN"


async def process_commands(session: AsyncSession, *, active: ActiveRuns) -> int:
    commands = (
        (
            await session.execute(
                select(Command)
                .where(
                    Command.state == CommandState.ACCEPTED,
                    Command.command_type == SAFE_STOP_COMMAND,
                )
                .order_by(Command.created_at, Command.id)
            )
        )
        .scalars()
        .all()
    )
    if not commands:
        return 0
    moment = datetime.now(UTC)
    for command in commands:
        command.state = CommandState.PROCESSING
        await session.flush()
        active.signal(command.target_id)
        command.state = CommandState.APPLIED
        command.applied_at = moment
    await session.commit()
    return len(commands)
