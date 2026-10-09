import subprocess
from pathlib import Path

from engine.base import EngineCapabilities, EngineDescriptor, EngineIdentity
from engine.siesta.native import ARTIFACT_CLASSES

ADAPTER_VERSION = "0.1.0"
ENGINE_FAMILY = "SIESTA"
NATIVE_STATE_FORMAT_VERSION = 1


def inspect_engine(source_root: Path) -> EngineDescriptor:
    return EngineDescriptor(
        identity=EngineIdentity(
            family=ENGINE_FAMILY,
            revision=_git_revision(Path(source_root)),
            adapter_version=ADAPTER_VERSION,
        ),
        capabilities=EngineCapabilities(
            autonomous_defaults=True,
            work_items=True,
            review=True,
            verification=True,
            learning=True,
        ),
    )


def capability_manifest() -> dict:
    return {
        "schema_version": 1,
        "interaction": {
            "human_requirements": False,
            "autonomous_defaults": True,
        },
        "run_control": {
            "safe_stop": False,
            "resume": False,
        },
        "work_items": True,
        "review": True,
        "verification": True,
        "learning": True,
        "runtime_smoke": True,
        "native_state_format_version": NATIVE_STATE_FORMAT_VERSION,
        "artifacts": list(ARTIFACT_CLASSES),
    }


def _git_revision(source_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(source_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip()
