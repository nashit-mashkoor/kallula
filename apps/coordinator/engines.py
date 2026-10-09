from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from coordinator.loop import EngineFactory
from coordinator.settings import CoordinatorSettings
from domain.states import EngineRuntimeState
from engine.base import Engine, EngineError
from engine.siesta import SiestaAdapter
from persistence import workspaces
from persistence.models import Run
from persistence.runtimes import ensure_run_runtime
from runtime.base.engine_runtime import EngineRuntimeManager
from runtime.base.storage import StorageError
from runtime.base.workspace import WorkspaceManager


def build_engine_factory(
    settings: CoordinatorSettings,
    *,
    extra_env: Mapping[str, str] | None = None,
) -> EngineFactory | None:
    if not settings.development_mode:
        return None
    source_root = Path(settings.engine_source_root)
    if not source_root.is_dir():
        return None
    workspace_manager = WorkspaceManager(settings.workspace_root)
    runtime_manager = EngineRuntimeManager(settings.workspace_root)

    async def factory(session: AsyncSession, run: Run) -> Engine:
        workspace = await workspaces.get_for_project(session, run.project_id)
        if workspace is None:
            raise EngineError(
                "COORDINATOR_WORKSPACE_MISSING",
                "The project workspace record is missing.",
            )
        try:
            workspace_path = workspace_manager.path_for(workspace.storage_key)
        except StorageError as exc:
            raise EngineError("COORDINATOR_WORKSPACE_UNAVAILABLE", exc.detail) from exc
        runtime = await ensure_run_runtime(session, run)
        try:
            runtime_path = runtime_manager.ensure(runtime.storage_key, source_root)
        except StorageError as exc:
            runtime.state = EngineRuntimeState.ERROR
            raise EngineError("COORDINATOR_RUNTIME_UNAVAILABLE", exc.detail) from exc
        if runtime.state is not EngineRuntimeState.READY:
            runtime.state = EngineRuntimeState.READY
            runtime.validated_at = datetime.now(UTC)
        return SiestaAdapter(
            source_root=source_root,
            runtime_path=runtime_path,
            workspace_path=workspace_path,
            objective=run.objective,
            poll_interval=settings.engine_poll_interval_seconds,
            extra_env=extra_env,
        )

    return factory
