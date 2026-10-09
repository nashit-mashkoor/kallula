import subprocess

import pytest

from runtime.base.storage import StorageError
from runtime.base.workspace import WorkspaceManager

STORAGE_KEY = "projects/project-1/workspace"


def test_allocate_creates_workspace_and_git_repository(tmp_path):
    manager = WorkspaceManager(tmp_path / "root")

    path = manager.allocate(STORAGE_KEY)

    assert path == (tmp_path / "root" / STORAGE_KEY).resolve()
    assert path.is_dir()
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "true"


def test_allocate_is_idempotent(tmp_path):
    manager = WorkspaceManager(tmp_path / "root")
    path = manager.allocate(STORAGE_KEY)
    marker = path / "marker.txt"
    marker.write_text("kept")

    again = manager.allocate(STORAGE_KEY)

    assert again == path
    assert marker.read_text() == "kept"


def test_allocate_rejects_relative_path_escape(tmp_path):
    manager = WorkspaceManager(tmp_path / "root")

    with pytest.raises(StorageError) as excinfo:
        manager.allocate("../outside")

    assert excinfo.value.code == "STORAGE_PATH_ESCAPE"
    assert not (tmp_path / "outside").exists()


def test_allocate_rejects_absolute_path(tmp_path):
    manager = WorkspaceManager(tmp_path / "root")

    with pytest.raises(StorageError) as excinfo:
        manager.allocate(str(tmp_path / "elsewhere"))

    assert excinfo.value.code == "STORAGE_PATH_ESCAPE"
    assert not (tmp_path / "elsewhere").exists()


def test_allocate_rejects_symlinked_projects_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "projects").symlink_to(outside)
    manager = WorkspaceManager(root)

    with pytest.raises(StorageError) as excinfo:
        manager.allocate(STORAGE_KEY)

    assert excinfo.value.code == "STORAGE_PATH_ESCAPE"
    assert list(outside.iterdir()) == []


def test_path_for_returns_allocated_workspace(tmp_path):
    manager = WorkspaceManager(tmp_path / "root")
    allocated = manager.allocate(STORAGE_KEY)

    assert manager.path_for(STORAGE_KEY) == allocated


def test_path_for_rejects_unallocated_workspace(tmp_path):
    manager = WorkspaceManager(tmp_path / "root")

    with pytest.raises(StorageError) as excinfo:
        manager.path_for(STORAGE_KEY)

    assert excinfo.value.code == "WORKSPACE_NOT_ALLOCATED"


def test_allocate_reports_unusable_root(tmp_path):
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    manager = WorkspaceManager(blocked)

    with pytest.raises(StorageError) as excinfo:
        manager.allocate(STORAGE_KEY)

    assert excinfo.value.code == "WORKSPACE_ALLOCATION_FAILED"
