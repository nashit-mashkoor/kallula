import shutil
from pathlib import Path

from runtime.base.storage import StorageError, resolve_under_root

FACTORY_ASSETS = ("config", "skills", "kb")


class EngineRuntimeManager:
    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def path_for(self, storage_key: str) -> Path:
        path = resolve_under_root(self._root, storage_key)
        if not self._is_materialized(path):
            raise StorageError(
                "ENGINE_RUNTIME_NOT_READY", "Engine runtime is not materialized."
            )
        return path

    def ensure(self, storage_key: str, installation_source: Path) -> Path:
        runtime = resolve_under_root(self._root, storage_key)
        if self._is_materialized(runtime):
            return runtime
        source = Path(installation_source)
        if any(not (source / name).is_dir() for name in FACTORY_ASSETS):
            raise StorageError(
                "ENGINE_RUNTIME_SOURCE_INVALID",
                "Engine installation is missing factory assets.",
            )
        try:
            runtime.mkdir(parents=True, exist_ok=True)
            for name in FACTORY_ASSETS:
                shutil.copytree(source / name, runtime / name, dirs_exist_ok=True)
        except OSError as exc:
            raise StorageError(
                "ENGINE_RUNTIME_MATERIALIZATION_FAILED",
                "Engine runtime could not be materialized.",
            ) from exc
        return resolve_under_root(self._root, storage_key)

    @staticmethod
    def _is_materialized(path: Path) -> bool:
        return (path / "config" / "models.json").is_file()
