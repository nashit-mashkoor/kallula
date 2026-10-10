import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from coordinator.loop import EngineFactory
from coordinator.settings import CoordinatorSettings
from domain.states import EngineRuntimeState
from engine.base import Engine, EngineError
from engine.siesta import SiestaAdapter, capability_manifest, inspect_engine
from persistence import installations as installations_repo
from persistence import workspaces
from persistence.models import EngineInstallation, Run
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
    source_root = Path(settings.engine_source_root).resolve()
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
            if settings.engine_models_config is not None:
                apply_models_config(runtime_path, Path(settings.engine_models_config))
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


def apply_models_config(runtime_path: Path, config_path: Path) -> None:
    try:
        content = json.loads(config_path.read_text())
    except (OSError, ValueError) as exc:
        raise EngineError(
            "COORDINATOR_MODELS_CONFIG_INVALID",
            "The engine model configuration is not readable.",
        ) from exc
    for role in ("planner", "worker", "consultant"):
        entry = content.get(role) if isinstance(content, dict) else None
        if (
            not isinstance(entry, dict)
            or "model" not in entry
            or "provider" not in entry
        ):
            raise EngineError(
                "COORDINATOR_MODELS_CONFIG_INVALID",
                f"The engine model configuration is missing the {role} role.",
            )
    try:
        (runtime_path / "config" / "models.json").write_text(
            json.dumps(content, indent=2) + "\n"
        )
    except OSError as exc:
        raise EngineError(
            "COORDINATOR_MODELS_CONFIG_INVALID",
            "The engine model configuration could not be applied.",
        ) from exc


async def register_pinned_installation(
    session: AsyncSession, settings: CoordinatorSettings
) -> EngineInstallation:
    source_root = Path(settings.engine_source_root).resolve()
    descriptor = inspect_engine(source_root)
    manifest = capability_manifest()
    digest = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                {
                    "family": descriptor.identity.family,
                    "revision": descriptor.identity.revision,
                    "adapter_version": descriptor.identity.adapter_version,
                    "manifest": manifest,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
    )
    return await installations_repo.register(
        session,
        engine_family=descriptor.identity.family,
        engine_revision=descriptor.identity.revision,
        adapter_version=descriptor.identity.adapter_version,
        installation_digest=digest,
        capability_manifest=manifest,
    )
