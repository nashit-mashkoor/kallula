import subprocess
from pathlib import Path

from engine.base import EngineCapabilities, EngineDescriptor, EngineIdentity
from engine.siesta.native import ARTIFACT_CLASSES

ADAPTER_VERSION = "0.2.0"
ENGINE_FAMILY = "SIESTA"
NATIVE_STATE_FORMAT_VERSION = 1


def supports_external_interaction(source_root: Path) -> bool:
    """True when the engine build carries the external interaction channel."""
    return (Path(source_root) / "pipeline" / "human.py").is_file()


def inspect_engine(source_root: Path) -> EngineDescriptor:
    source_root = Path(source_root)
    return EngineDescriptor(
        identity=EngineIdentity(
            family=ENGINE_FAMILY,
            revision=_git_revision(source_root),
            adapter_version=ADAPTER_VERSION,
        ),
        capabilities=EngineCapabilities(
            human_requirements=supports_external_interaction(source_root),
            autonomous_defaults=True,
            safe_stop=True,
            work_items=True,
            review=True,
            verification=True,
            learning=True,
        ),
    )


def capability_manifest(source_root: Path) -> dict:
    return {
        "schema_version": 1,
        "interaction": {
            "human_requirements": supports_external_interaction(source_root),
            "autonomous_defaults": True,
        },
        "run_control": {
            "safe_stop": True,
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
