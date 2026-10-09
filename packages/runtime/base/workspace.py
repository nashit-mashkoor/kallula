import subprocess
from pathlib import Path

from runtime.base.storage import StorageError, resolve_under_root


class WorkspaceManager:
    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def path_for(self, storage_key: str) -> Path:
        path = resolve_under_root(self._root, storage_key)
        if not path.is_dir():
            raise StorageError("WORKSPACE_NOT_ALLOCATED", "Workspace is not allocated.")
        return path

    def allocate(self, storage_key: str) -> Path:
        path = resolve_under_root(self._root, storage_key)
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageError(
                "WORKSPACE_ALLOCATION_FAILED",
                "Workspace directory could not be created.",
            ) from exc
        resolved = resolve_under_root(self._root, storage_key)
        if not resolved.is_dir():
            raise StorageError(
                "WORKSPACE_ALLOCATION_FAILED",
                "Workspace directory could not be created.",
            )
        self._ensure_git(resolved)
        return resolved

    def _ensure_git(self, path: Path) -> None:
        if (path / ".git").exists():
            return
        try:
            subprocess.run(
                ["git", "init", "-b", "main", str(path)],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise StorageError(
                "WORKSPACE_GIT_UNAVAILABLE", "Git is not available."
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise StorageError(
                "WORKSPACE_GIT_INIT_FAILED",
                "Git repository could not be initialized.",
            ) from exc
