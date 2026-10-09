import json
import re
from dataclasses import dataclass
from pathlib import Path

from engine.base import EngineOutcome, EngineStage, StageCategory
from engine.siesta.errors import SiestaAdapterError

ISSUE_HEADER = re.compile(r"^##[ \t]+Issue[ \t]+#(\d+)", re.MULTILINE)
ISSUE_NUMBER = re.compile(r"[Ii]ssue #(\d+)")

PHASE_STAGES = {
    "phase-0": StageCategory.REQUIREMENTS,
    "phase-1": StageCategory.SPECIFICATION,
    "phase-2": StageCategory.PLANNING,
    "phase-3": StageCategory.EXECUTION,
    "phase-4": StageCategory.REVIEW,
    "phase-5": StageCategory.VERIFICATION,
}

STAGE_SEQUENCE = (
    StageCategory.REQUIREMENTS,
    StageCategory.SPECIFICATION,
    StageCategory.PLANNING,
    StageCategory.EXECUTION,
    StageCategory.REVIEW,
    StageCategory.VERIFICATION,
    StageCategory.LEARNING,
)

STAGE_LABELS = {
    StageCategory.REQUIREMENTS: "Requirements",
    StageCategory.SPECIFICATION: "Specification",
    StageCategory.PLANNING: "Planning",
    StageCategory.EXECUTION: "Execution",
    StageCategory.REVIEW: "Review",
    StageCategory.VERIFICATION: "Verification",
    StageCategory.LEARNING: "Learning",
}

ARTIFACT_PATTERNS = (
    ("intent_transcript", "interview_output.txt"),
    ("intent_closeout_evidence", "interview_closeout.txt"),
    ("specification", "spec.md"),
    ("implementation_plan", "issues.md"),
    ("project_knowledge", "kb/graph.json"),
    ("knowledge_schema", "kb/schema.json"),
    ("engine_checkpoint", ".pipeline-checkpoint"),
    ("engine_idea_record", ".pipeline-idea"),
    ("verification_verdict", "verify_verdict.txt"),
    ("issue_output", "issue_*_output.txt"),
    ("test_evidence", "regression_*.log"),
    ("pre_issue_context", "pre_issue_*.json"),
    ("issue_learning", "learning_issue_*.txt"),
    ("project_learning", "project_learning.*"),
    ("recovery_archive", ".git/siesta-recovery"),
)

ARTIFACT_CLASSES = tuple(sorted({name for name, _ in ARTIFACT_PATTERNS}))


@dataclass(frozen=True)
class NativeArtifact:
    normalized_class: str
    path: Path


@dataclass(frozen=True)
class NativeState:
    checkpoint: str | None
    issues: tuple[int, ...]
    started_issues: tuple[int, ...]
    completed_issues: tuple[int, ...]
    blocked_issues: tuple[int, ...]
    verdict: str | None
    failed: bool


def make_stage(category: StageCategory, native_id: str | None = None) -> EngineStage:
    return EngineStage(
        category=category,
        display_label=STAGE_LABELS[category],
        order=STAGE_SEQUENCE.index(category) + 1,
        native_id=native_id,
    )


def project_slug(idea: str) -> str:
    name = re.sub(r"[^a-z0-9]+", "-", idea.lower()).strip("-")
    if len(name) > 40:
        name = re.sub(r"-[^-]*$", "", name[:40])
    if not name:
        raise SiestaAdapterError(
            "SIESTA_OBJECTIVE_INVALID",
            "The run objective does not produce a usable project name.",
        )
    return name


def inspect_workspace(workspace: Path) -> NativeState:
    workspace = Path(workspace)
    checkpoint = _read_text(workspace / ".pipeline-checkpoint")
    if checkpoint is not None:
        checkpoint = checkpoint.strip() or None
    issues = tuple(
        int(match.group(1))
        for match in ISSUE_HEADER.finditer(_read_text(workspace / "issues.md") or "")
    )
    started = tuple(sorted(_numbered_evidence(workspace, "pre_issue_*.json")))
    completed, blocked, failed = _read_ledger(workspace / "kb" / "graph.json")
    verdict = _read_text(workspace / "verify_verdict.txt")
    if verdict is not None:
        verdict = verdict.strip() or None
    return NativeState(
        checkpoint=checkpoint,
        issues=issues,
        started_issues=started,
        completed_issues=completed,
        blocked_issues=blocked,
        verdict=verdict,
        failed=failed,
    )


def discover_artifacts(workspace: Path) -> list[NativeArtifact]:
    workspace = Path(workspace)
    found: list[NativeArtifact] = []
    for normalized_class, pattern in ARTIFACT_PATTERNS:
        for path in sorted(workspace.glob(pattern)):
            found.append(NativeArtifact(normalized_class, path))
    return found


def classify_outcome(
    state: NativeState, returncode: int | None
) -> tuple[EngineOutcome, str | None]:
    verified = (
        state.checkpoint == "complete"
        and state.verdict == "VERIFY_PASSED"
        and not state.blocked_issues
    )
    if verified:
        return EngineOutcome.COMPLETED_VERIFIED, None
    if state.failed:
        return (
            EngineOutcome.FAILED,
            "The engine recorded a pipeline failure in the project knowledge base.",
        )
    if state.checkpoint is None and state.verdict is None and not state.issues:
        return (
            EngineOutcome.FAILED,
            f"The engine exited with status {returncode} before producing project state.",
        )
    details = []
    if state.verdict is not None:
        details.append(f"verdict {state.verdict}")
    if state.blocked_issues:
        blocked = ", ".join(f"#{number}" for number in state.blocked_issues)
        details.append(f"blocked issues {blocked}")
    if state.checkpoint is not None:
        details.append(f"checkpoint {state.checkpoint}")
    summary = "The engine finished without verified completion"
    if details:
        summary += ": " + "; ".join(details)
    summary += "."
    return EngineOutcome.TERMINAL_UNVERIFIED_OR_INCOMPLETE, summary


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return None


def _numbered_evidence(workspace: Path, pattern: str) -> set[int]:
    numbers: set[int] = set()
    for path in workspace.glob(pattern):
        match = re.search(r"(\d+)", path.name)
        if match:
            numbers.add(int(match.group(1)))
    return numbers


def _read_ledger(path: Path) -> tuple[tuple[int, ...], tuple[int, ...], bool]:
    raw = _read_text(path)
    if raw is None or not raw.strip():
        return (), (), False
    try:
        ledger = json.loads(raw)
    except ValueError as exc:
        raise SiestaAdapterError(
            "SIESTA_NATIVE_STATE_INVALID",
            "The project knowledge base is not readable.",
        ) from exc
    completed: set[int] = set()
    blocked: set[int] = set()
    failed = False
    for node in ledger.get("nodes", []):
        node_type = node.get("type")
        summary = str(node.get("summary", ""))
        if node_type == "decision":
            match = re.fullmatch(r"Issue #(\d+) completed", summary)
            if match:
                completed.add(int(match.group(1)))
        elif node_type == "blocker":
            match = ISSUE_NUMBER.search(summary)
            if match:
                blocked.add(int(match.group(1)))
            elif summary == "Pipeline failed":
                failed = True
    return tuple(sorted(completed)), tuple(sorted(blocked)), failed
