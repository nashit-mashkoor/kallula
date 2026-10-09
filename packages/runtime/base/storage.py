from pathlib import Path


class StorageError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def resolve_under_root(root: Path, storage_key: str) -> Path:
    resolved_root = root.resolve()
    key_path = Path(storage_key)
    if not storage_key or key_path.is_absolute():
        raise StorageError("STORAGE_PATH_ESCAPE", "Storage key must be relative.")
    resolved = (resolved_root / key_path).resolve()
    if not resolved.is_relative_to(resolved_root):
        raise StorageError(
            "STORAGE_PATH_ESCAPE", "Storage path escapes the storage root."
        )
    return resolved
