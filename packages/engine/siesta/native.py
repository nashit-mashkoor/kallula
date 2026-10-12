import json
import mimetypes
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from engine.base import (
    EngineInteraction,
    EngineOutcome,
    EngineStage,
    StageCategory,
)
from engine.siesta.errors import SiestaAdapterError

ISSUE_HEADER = re.compile(
    r"^##[ \t]+Issue[ \t]+#(\d+)[ \t]*:?[ \t]*(.*)$", re.MULTILINE
)
ISSUE_NUMBER = re.compile(r"[Ii]ssue #(\d+)")
STOP_MARKER = "stop.md"
INTERACTION_STATE_FILE = ".pipeline-interaction.json"
INTERACTION_RESPONSE_FILE = "interaction-response.json"

# Native interaction kinds map to the stable Kallula interaction purposes
# (API & Data Contract Specification section 26.2). Unknown future kinds are
# surfaced as a question rather than leaking native identifiers.
INTERACTION_KINDS = {
    "requirements_question": "QUESTION",
    "intent_confirmation": "FINAL_INTENT_CONFIRMATION",
}

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
    ("INTERVIEW_TRANSCRIPT", "interview_output.txt"),
    ("INTERVIEW_TRANSCRIPT", "interview_closeout.txt"),
    ("SPECIFICATION", "spec.md"),
    ("PLAN", "issues.md"),
    ("KNOWLEDGE", "kb/graph.json"),
    ("KNOWLEDGE", "kb/schema.json"),
    ("ENGINE_CHECKPOINT", ".pipeline-checkpoint"),
    ("OTHER", ".pipeline-idea"),
    ("VERIFICATION_EVIDENCE", "verify_verdict.txt"),
    ("OTHER", "issue_*_output.txt"),
    ("TEST_EVIDENCE", "regression_*.log"),
    ("OTHER", "pre_issue_*.json"),
    ("LEARNING", "learning_issue_*.txt"),
    ("LEARNING", "project_learning.*"),
    ("RECOVERY", ".git/siesta-recovery"),
)

ARTIFACT_CLASSES = tuple(sorted({name for name, _ in ARTIFACT_PATTERNS}))


@dataclass(frozen=True)
class NativeArtifact:
    artifact_class: str
    display_name: str
    relative_path: str
    path: Path


@dataclass(frozen=True)
class NativeIssue:
    number: int
    title: str
    started: bool
    completed: bool
    blocked: bool
    blocker: str | None


@dataclass(frozen=True)
class NativeState:
    checkpoint: str | None
    issues: tuple[NativeIssue, ...]
    verdict: str | None
    failed: bool
    stopped: bool = False
    interaction: EngineInteraction | None = None


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


def normalize_idea(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def inspect_workspace(workspace: Path) -> NativeState:
    workspace = Path(workspace)
    checkpoint = _read_text(workspace / ".pipeline-checkpoint")
    if checkpoint is not None:
        checkpoint = checkpoint.strip() or None
    discovered = _discovered_issues(workspace / "issues.md")
    started = _numbered_evidence(workspace, "pre_issue_*.json")
    completed, blockers, failed = _read_ledger(workspace / "kb" / "graph.json")
    issues = tuple(
        NativeIssue(
            number=number,
            title=title,
            started=number in started,
            completed=number in completed,
            blocked=number in blockers,
            blocker=blockers.get(number),
        )
        for number, title in discovered
    )
    verdict = _read_text(workspace / "verify_verdict.txt")
    if verdict is not None:
        verdict = verdict.strip() or None
    stopped = (workspace / STOP_MARKER).is_file()
    return NativeState(
        checkpoint=checkpoint,
        issues=issues,
        verdict=verdict,
        failed=failed,
        stopped=stopped,
        interaction=read_interaction(workspace),
    )


def read_interaction(workspace: Path) -> EngineInteraction | None:
    """The native pending interaction, if one is open (not yet consumed)."""
    raw = _read_text(Path(workspace) / INTERACTION_STATE_FILE)
    if raw is None:
        return None
    try:
        state = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(state, dict) or state.get("consumed"):
        return None
    interaction_id = state.get("interaction_id")
    kind = state.get("kind")
    question = state.get("question")
    if not interaction_id or not kind or not question:
        return None
    recommendation = state.get("recommendation")
    return EngineInteraction(
        native_id=str(interaction_id),
        kind=INTERACTION_KINDS.get(str(kind), "QUESTION"),
        question=str(question),
        recommendation=str(recommendation) if recommendation else None,
        final=bool(state.get("final")),
    )


def discover_artifacts(workspace: Path) -> list[NativeArtifact]:
    workspace = Path(workspace)
    found: list[NativeArtifact] = []
    for artifact_class, pattern in ARTIFACT_PATTERNS:
        for path in sorted(workspace.glob(pattern)):
            relative = path.relative_to(workspace).as_posix()
            found.append(
                NativeArtifact(
                    artifact_class=artifact_class,
                    display_name=artifact_display_name(relative),
                    relative_path=relative,
                    path=path,
                )
            )
    return found


def artifact_display_name(relative_path: str) -> str:
    fixed = {
        "interview_output.txt": "Interview transcript",
        "interview_closeout.txt": "Interview closeout",
        "spec.md": "Specification",
        "issues.md": "Implementation plan",
        "kb/graph.json": "Project knowledge",
        "kb/schema.json": "Knowledge schema",
        ".pipeline-checkpoint": "Engine checkpoint",
        ".pipeline-idea": "Engine idea record",
        "verify_verdict.txt": "Verification verdict",
        "project_learning.log": "Project learning",
    }
    if relative_path in fixed:
        return fixed[relative_path]
    name = relative_path.rsplit("/", 1)[-1]
    number = _trailing_number(name)
    if number is not None:
        if name.startswith("regression_"):
            return f"Test evidence for issue {number}"
        if name.startswith("issue_"):
            return f"Issue {number} output"
        if name.startswith("pre_issue_"):
            return f"Pre-issue context for issue {number}"
        if name.startswith("learning_issue_"):
            return f"Learning for issue {number}"
    if relative_path.startswith(".git/siesta-recovery"):
        return "Recovery archive"
    if name.startswith("project_learning"):
        return "Project learning"
    return "Artifact"


def classify_outcome(
    state: NativeState, returncode: int | None
) -> tuple[EngineOutcome, str | None]:
    if state.interaction is not None:
        # The engine persisted the pending interaction before exiting; the
        # worker is released and the answer resumes the Run later.
        return EngineOutcome.WAITING_FOR_HUMAN, None
    blocked = [issue.number for issue in state.issues if issue.blocked]
    verified = (
        state.checkpoint == "complete"
        and state.verdict == "VERIFY_PASSED"
        and not blocked
    )
    if verified:
        return EngineOutcome.COMPLETED_VERIFIED, None
    if state.stopped:
        return EngineOutcome.STOPPED_SAFE, None
    details = []
    if state.verdict is not None:
        details.append(f"verdict {state.verdict}")
    if blocked:
        details.append("blocked issues " + ", ".join(f"#{n}" for n in blocked))
    if state.checkpoint is not None:
        details.append(f"checkpoint {state.checkpoint}")
    if state.verdict is not None or blocked:
        summary = "The engine finished without verified completion"
        if details:
            summary += ": " + "; ".join(details)
        return EngineOutcome.TERMINAL_UNVERIFIED_OR_INCOMPLETE, summary + "."
    if state.failed:
        return (
            EngineOutcome.FAILED,
            "The engine recorded a pipeline failure in the project knowledge base.",
        )
    if state.checkpoint is None and not state.issues:
        if returncode is None:
            return (
                EngineOutcome.FAILED,
                "The engine exited before producing project state.",
            )
        return (
            EngineOutcome.FAILED,
            f"The engine exited with status {returncode} before producing project state.",
        )
    summary = "The engine finished without verified completion"
    if details:
        summary += ": " + "; ".join(details)
    return EngineOutcome.TERMINAL_UNVERIFIED_OR_INCOMPLETE, summary + "."


def _trailing_number(name: str) -> int | None:
    match = re.search(r"_(\d+)", name)
    return int(match.group(1)) if match else None


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return None


def _discovered_issues(path: Path) -> list[tuple[int, str]]:
    raw = _read_text(path) or ""
    return [
        (int(match.group(1)), match.group(2).strip())
        for match in ISSUE_HEADER.finditer(raw)
    ]


def _numbered_evidence(workspace: Path, pattern: str) -> set[int]:
    numbers: set[int] = set()
    for path in workspace.glob(pattern):
        match = re.search(r"(\d+)", path.name)
        if match:
            numbers.add(int(match.group(1)))
    return numbers


def write_stop_marker(workspace: Path) -> None:
    marker = Path(workspace) / STOP_MARKER
    if not marker.exists():
        marker.write_text("Safe stop requested by Kallula.\n")


def clear_stop_marker(workspace: Path) -> None:
    workspace = Path(workspace)
    marker = workspace / STOP_MARKER
    if not marker.exists():
        return
    tracked = _is_tracked(workspace, STOP_MARKER)
    marker.unlink()
    if tracked:
        _commit_marker_removal(workspace)


def _is_tracked(workspace: Path, name: str) -> bool:
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", name],
        cwd=workspace,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _commit_marker_removal(workspace: Path) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Kallula",
        "GIT_AUTHOR_EMAIL": "kallula@localhost",
        "GIT_COMMITTER_NAME": "Kallula",
        "GIT_COMMITTER_EMAIL": "kallula@localhost",
    }
    subprocess.run(
        ["git", "add", "--", STOP_MARKER],
        cwd=workspace,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    subprocess.run(
        ["git", "commit", "-m", "Clear safe-stop marker after safe stop"],
        cwd=workspace,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _read_ledger(
    path: Path,
) -> tuple[set[int], dict[int, str], bool]:
    raw = _read_text(path)
    if raw is None or not raw.strip():
        return set(), {}, False
    try:
        ledger = json.loads(raw)
    except ValueError as exc:
        raise SiestaAdapterError(
            "SIESTA_NATIVE_STATE_INVALID",
            "The project knowledge base is not readable.",
        ) from exc
    completed: set[int] = set()
    blockers: dict[int, str] = {}
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
                blockers[int(match.group(1))] = summary
            elif summary == "Pipeline failed":
                failed = True
    return completed, blockers, failed


def media_type_for(path: Path) -> str | None:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed
