import os
from collections.abc import Mapping
from pathlib import Path

BASE_ENV_KEYS = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")

GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "Kallula",
    "GIT_AUTHOR_EMAIL": "kallula@localhost",
    "GIT_COMMITTER_NAME": "Kallula",
    "GIT_COMMITTER_EMAIL": "kallula@localhost",
}


def build_child_env(
    *,
    source_root: Path,
    runtime_path: Path,
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = {key: os.environ[key] for key in BASE_ENV_KEYS if key in os.environ}
    env["SIESTA_FACTORY"] = str(Path(runtime_path).resolve())
    env["PYTHONPATH"] = str(Path(source_root).resolve())
    env.update(GIT_IDENTITY)
    if extra:
        env.update(extra)
    return env
