from pathlib import Path

from engine.siesta import (
    ADAPTER_VERSION,
    build_child_env,
    capability_manifest,
    inspect_engine,
)

VENDOR_FACTORY = Path(__file__).resolve().parents[2] / "vendor/siesta/factory"


def test_inspect_engine_reports_pinned_revision():
    descriptor = inspect_engine(VENDOR_FACTORY)

    assert descriptor.identity.family == "SIESTA"
    assert descriptor.identity.revision == "20b149e0734b09730dfd22803d2695776fcf84b8"
    assert descriptor.identity.adapter_version == ADAPTER_VERSION
    assert descriptor.capabilities.autonomous_defaults is True
    assert descriptor.capabilities.work_items is True
    assert descriptor.capabilities.review is True
    assert descriptor.capabilities.verification is True
    assert descriptor.capabilities.learning is True
    assert descriptor.capabilities.human_requirements is False
    assert descriptor.capabilities.safe_stop is False
    assert descriptor.capabilities.resume is False


def test_capability_manifest_is_honest_for_this_milestone():
    manifest = capability_manifest()

    assert manifest["interaction"] == {
        "human_requirements": False,
        "autonomous_defaults": True,
    }
    assert manifest["run_control"] == {"safe_stop": False, "resume": False}
    assert manifest["native_state_format_version"] == 1
    assert "VERIFICATION_EVIDENCE" in manifest["artifacts"]


def test_child_env_is_explicitly_allowlisted(monkeypatch):
    monkeypatch.setenv("KALLULA_TEST_SECRET", "sentinel")

    env = build_child_env(
        source_root=Path("/engine/source"),
        runtime_path=Path("/run/runtime"),
        extra={"PI_CODING_AGENT_DIR": "/pi-profile"},
    )

    assert "KALLULA_TEST_SECRET" not in env
    assert env["SIESTA_FACTORY"] == "/run/runtime"
    assert env["PYTHONPATH"] == "/engine/source"
    assert env["PI_CODING_AGENT_DIR"] == "/pi-profile"
    assert env["GIT_AUTHOR_EMAIL"] == "kallula@localhost"
    allowed = {
        "PATH",
        "HOME",
        "LANG",
        "LC_ALL",
        "TMPDIR",
        "SIESTA_FACTORY",
        "PYTHONPATH",
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
        "PI_CODING_AGENT_DIR",
    }
    assert set(env) <= allowed
