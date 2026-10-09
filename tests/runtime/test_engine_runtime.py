import shutil

import pytest

from runtime.base.engine_runtime import EngineRuntimeManager
from runtime.base.storage import StorageError

STORAGE_KEY = "projects/project-1/runs/run-1/engine-runtime"


def make_installation(root):
    (root / "config").mkdir(parents=True)
    (root / "config" / "models.json").write_text('{"planner": {"model": "m"}}')
    skill = root / "skills" / "issue-executor"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Issue executor")
    (root / "kb").mkdir()
    (root / "kb" / "schema.json").write_text('{"node_types": {}}')
    (root / "kb" / "global-seed.json").write_text('{"nodes": [], "edges": []}')
    return root


def test_ensure_materializes_runtime_from_installation(tmp_path):
    installation = make_installation(tmp_path / "installation")
    manager = EngineRuntimeManager(tmp_path / "root")

    runtime = manager.ensure(STORAGE_KEY, installation)

    assert runtime == (tmp_path / "root" / STORAGE_KEY).resolve()
    assert (runtime / "config" / "models.json").is_file()
    assert (runtime / "skills" / "issue-executor" / "SKILL.md").is_file()
    assert (runtime / "kb" / "schema.json").is_file()
    assert (runtime / "kb" / "global-seed.json").is_file()


def test_ensure_reuses_runtime_and_preserves_state(tmp_path):
    installation = make_installation(tmp_path / "installation")
    manager = EngineRuntimeManager(tmp_path / "root")
    runtime = manager.ensure(STORAGE_KEY, installation)
    learned = runtime / "kb" / "global-graph.json"
    learned.write_text('{"nodes": [{"id": "n1"}], "edges": []}')
    skill = runtime / "skills" / "issue-executor" / "SKILL.md"
    skill.write_text("# Improved")

    again = manager.ensure(STORAGE_KEY, installation)

    assert again == runtime
    assert learned.read_text() == '{"nodes": [{"id": "n1"}], "edges": []}'
    assert skill.read_text() == "# Improved"


def test_ensure_rejects_invalid_installation_source(tmp_path):
    installation = make_installation(tmp_path / "installation")
    shutil.rmtree(installation / "kb")
    manager = EngineRuntimeManager(tmp_path / "root")

    with pytest.raises(StorageError) as excinfo:
        manager.ensure(STORAGE_KEY, installation)

    assert excinfo.value.code == "ENGINE_RUNTIME_SOURCE_INVALID"
    assert not (tmp_path / "root" / STORAGE_KEY).exists()


def test_ensure_rejects_path_escape(tmp_path):
    installation = make_installation(tmp_path / "installation")
    manager = EngineRuntimeManager(tmp_path / "root")

    with pytest.raises(StorageError) as excinfo:
        manager.ensure("../outside", installation)

    assert excinfo.value.code == "STORAGE_PATH_ESCAPE"
    assert not (tmp_path / "outside").exists()


def test_path_for_requires_materialized_runtime(tmp_path):
    installation = make_installation(tmp_path / "installation")
    manager = EngineRuntimeManager(tmp_path / "root")

    with pytest.raises(StorageError) as excinfo:
        manager.path_for(STORAGE_KEY)

    assert excinfo.value.code == "ENGINE_RUNTIME_NOT_READY"

    materialized = manager.ensure(STORAGE_KEY, installation)

    assert manager.path_for(STORAGE_KEY) == materialized
