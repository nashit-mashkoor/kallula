import subprocess
from pathlib import Path


class WorkspaceError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkspaceManager:
    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def path_for(self, storage_key: str) -> Path:
        path = self._resolve(storage_key)
        if not path.is_dir():
            raise WorkspaceError(
                "WORKSPACE_NOT_ALLOCATED", "Workspace is not allocated."
            )
        return path

    def allocate(self, storage_key: str) -> Path:
        path = self._resolve(storage_key)
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise WorkspaceError(
                "WORKSPACE_ALLOCATION_FAILED",
                "Workspace directory could not be created.",
            ) from exc
        resolved = path.resolve()
        if not resolved.is_relative_to(self._root.resolve()) or not resolved.is_dir():
            raise WorkspaceError(
                "WORKSPACE_PATH_ESCAPE", "Workspace path escapes the workspace root."
            )
        self._ensure_git(resolved)
        return resolved

    def _resolve(self, storage_key: str) -> Path:
        root = self._root.resolve()
        key_path = Path(storage_key)
        if not storage_key or key_path.is_absolute():
            raise WorkspaceError(
                "WORKSPACE_PATH_ESCAPE",
                "Workspace storage key must be relative.",
            )
        resolved = (root / key_path).resolve()
        if not resolved.is_relative_to(root):
            raise WorkspaceError(
                "WORKSPACE_PATH_ESCAPE", "Workspace path escapes the workspace root."
            )
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
            raise WorkspaceError(
                "WORKSPACE_GIT_UNAVAILABLE", "Git is not available."
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise WorkspaceError(
                "WORKSPACE_GIT_INIT_FAILED",
                "Git repository could not be initialized.",
            ) from exc
