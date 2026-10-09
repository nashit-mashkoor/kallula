from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.models import Run, RunEngineRuntime


def runtime_storage_key(run: Run) -> str:
    return f"projects/{run.project_id}/runs/{run.id}/engine-runtime"


async def get_run_runtime(
    session: AsyncSession, run_id: str
) -> RunEngineRuntime | None:
    return (
        await session.execute(
            select(RunEngineRuntime).where(RunEngineRuntime.run_id == run_id)
        )
    ).scalar_one_or_none()


async def ensure_run_runtime(session: AsyncSession, run: Run) -> RunEngineRuntime:
    runtime = await get_run_runtime(session, run.id)
    if runtime is not None:
        return runtime
    runtime = RunEngineRuntime(
        run_id=run.id,
        storage_driver="local",
        storage_key=runtime_storage_key(run),
    )
    session.add(runtime)
    await session.flush()
    return runtime
