import subprocess
from pathlib import Path

import pytest

VENDOR_ENGINE = Path(__file__).resolve().parents[1] / "vendor" / "siesta"


def _vendor_revision() -> str:
    result = subprocess.run(
        ["git", "-C", str(VENDOR_ENGINE), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@pytest.fixture(scope="session")
def pinned_engine_revision() -> str:
    """The submodule revision the vendored engine is pinned to."""
    return _vendor_revision()
