import asyncio
import hashlib
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from domain.states import EventSeverity
from engine.base import (
    EngineDescriptor,
    EngineEvent,
    EngineHooks,
    EngineResult,
    EngineRunRequest,
    EngineStage,
    StageCategory,
)
from engine.siesta.env import build_child_env
from engine.siesta.errors import SiestaAdapterError
from engine.siesta.identity import inspect_engine
from engine.siesta.native import (
    PHASE_STAGES,
    STAGE_SEQUENCE,
    NativeArtifact,
    NativeState,
    classify_outcome,
    discover_artifacts,
    inspect_workspace,
    make_stage,
    media_type_for,
    project_slug,
)

PHASE_SEQUENCE = tuple(PHASE_STAGES)


class SiestaAdapter:
    def __init__(
        self,
        *,
        source_root: Path,
        runtime_path: Path,
        workspace_path: Path,
        objective: str,
        poll_interval: float = 0.5,
        extra_env: Mapping[str, str] | None = None,
    ) -> None:
        self._source_root = Path(source_root)
        self._runtime_path = Path(runtime_path)
        self._workspace_path = Path(workspace_path)
        self._objective = objective
        self._poll_interval = poll_interval
        self._extra_env = extra_env

    def describe(self) -> EngineDescriptor:
        return inspect_engine(self._source_root)

    async def run(self, request: EngineRunRequest, hooks: EngineHooks) -> EngineResult:
        self._prepare_launch()
        env = build_child_env(
            source_root=self._source_root,
            runtime_path=self._runtime_path,
            extra=self._extra_env,
        )
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "pipeline",
                self._objective,
                "--auto",
                cwd=str(self._runtime_path),
                env=env,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise SiestaAdapterError(
                "SIESTA_LAUNCH_FAILED", "The engine process could not be started."
            ) from exc

        stdout_task = asyncio.create_task(_drain(process.stdout))
        stderr_task = asyncio.create_task(_drain(process.stderr))
        emitter = _EventEmitter(hooks)
        try:
            await emitter.begin()
            while True:
                await emitter.inspect(self._workspace_path)
                try:
                    await asyncio.wait_for(process.wait(), timeout=self._poll_interval)
                    break
                except TimeoutError:
                    continue
            await emitter.inspect(self._workspace_path)
        except BaseException:
            if process.returncode is None:
                process.kill()
                await process.wait()
            stdout_task.cancel()
            stderr_task.cancel()
            raise

        await stdout_task
        await stderr_task
        native = inspect_workspace(self._workspace_path)
        outcome, summary = classify_outcome(native, process.returncode)
        return EngineResult(outcome=outcome, failure_summary=summary)

    def _prepare_launch(self) -> None:
        workspace = self._workspace_path.resolve()
        projects_dir = self._runtime_path / "projects"
        projects_dir.mkdir(parents=True, exist_ok=True)
        link = projects_dir / project_slug(self._objective)
        if link.is_symlink():
            if link.resolve() != workspace:
                raise SiestaAdapterError(
                    "SIESTA_WORKSPACE_INJECTION_FAILED",
                    "The run runtime is bound to a different workspace.",
                )
        elif link.exists():
            raise SiestaAdapterError(
                "SIESTA_WORKSPACE_INJECTION_FAILED",
                "The run runtime contains a project directory that is not the "
                "canonical workspace.",
            )
        else:
            link.symlink_to(workspace, target_is_directory=True)
        self._link_adapted_skills()

    def _link_adapted_skills(self) -> None:
        source_agents = self._source_root.parent / ".agents"
        if not source_agents.is_dir():
            return
        target = self._runtime_path.parent / ".agents"
        if target.is_symlink():
            if target.resolve() != source_agents.resolve():
                raise SiestaAdapterError(
                    "SIESTA_SKILL_SOURCE_CONFLICT",
                    "The run runtime is bound to a different skill source.",
                )
            return
        if target.exists():
            raise SiestaAdapterError(
                "SIESTA_SKILL_SOURCE_CONFLICT",
                "The run runtime parent contains a foreign .agents directory.",
            )
        target.symlink_to(source_agents.resolve(), target_is_directory=True)


async def _drain(stream: asyncio.StreamReader) -> str:
    data = await stream.read()
    return data.decode(errors="replace")


def _git_source_identity(workspace: Path) -> dict:
    try:
        result = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return {}
    return {"git_commit": result.stdout.strip()}


class _EventEmitter:
    def __init__(self, hooks: EngineHooks) -> None:
        self._hooks = hooks
        self._sequence = 0
        self._completed_stages = 0
        self._discovered: set[int] = set()
        self._started: set[int] = set()
        self._blocked: set[int] = set()
        self._completed: set[int] = set()
        self._verdict_emitted = False
        self._artifacts: set[str] = set()

    async def begin(self) -> None:
        await self._emit_stage("STAGE_STARTED", StageCategory.REQUIREMENTS)

    async def inspect(self, workspace: Path) -> None:
        state = inspect_workspace(workspace)
        await self._emit_stage_progress(state)
        await self._emit_work_items(state)
        await self._emit_verification(state)
        await self._emit_artifacts(workspace)

    async def _emit_stage_progress(self, state: NativeState) -> None:
        traversed = 0
        if state.checkpoint in PHASE_SEQUENCE:
            traversed = PHASE_SEQUENCE.index(state.checkpoint) + 1
        elif state.checkpoint == "complete":
            traversed = len(STAGE_SEQUENCE)
        for index in range(self._completed_stages, traversed):
            stage = STAGE_SEQUENCE[index]
            native_id = PHASE_SEQUENCE[index] if index < len(PHASE_SEQUENCE) else None
            await self._emit_stage("STAGE_COMPLETED", stage, native_id=native_id)
            if index + 1 < len(STAGE_SEQUENCE):
                await self._emit_stage("STAGE_STARTED", STAGE_SEQUENCE[index + 1])
        self._completed_stages = max(self._completed_stages, traversed)

    async def _emit_work_items(self, state: NativeState) -> None:
        stage = make_stage(StageCategory.EXECUTION)
        for issue in state.issues:
            if issue.number in self._discovered:
                continue
            self._discovered.add(issue.number)
            await self._emit(
                "WORK_ITEM_DISCOVERED",
                "WORK_ITEM",
                f"Work item {issue.number} discovered.",
                stage=stage,
                work_item_native_id=str(issue.number),
                payload={"title": issue.title},
            )
        for issue in state.issues:
            if not issue.started or issue.number in self._started:
                continue
            self._started.add(issue.number)
            await self._emit(
                "WORK_ITEM_STARTED",
                "WORK_ITEM",
                f"Work item {issue.number} started.",
                stage=stage,
                work_item_native_id=str(issue.number),
            )
        for issue in state.issues:
            if not issue.blocked or issue.number in self._blocked:
                continue
            self._blocked.add(issue.number)
            await self._emit(
                "WORK_ITEM_BLOCKED",
                "WORK_ITEM",
                f"Work item {issue.number} blocked.",
                severity=EventSeverity.WARNING,
                stage=stage,
                work_item_native_id=str(issue.number),
                payload={"blocker": issue.blocker},
            )
        for issue in state.issues:
            if not issue.completed or issue.number in self._completed:
                continue
            self._completed.add(issue.number)
            await self._emit(
                "WORK_ITEM_COMPLETED",
                "WORK_ITEM",
                f"Work item {issue.number} completed.",
                stage=stage,
                work_item_native_id=str(issue.number),
            )

    async def _emit_verification(self, state: NativeState) -> None:
        if state.verdict is None or self._verdict_emitted:
            return
        self._verdict_emitted = True
        severity = (
            EventSeverity.INFO
            if state.verdict == "VERIFY_PASSED"
            else EventSeverity.WARNING
        )
        await self._emit(
            "VERIFICATION_COMPLETED",
            "VERIFICATION",
            f"Verification finished with {state.verdict}.",
            severity=severity,
            stage=make_stage(StageCategory.VERIFICATION),
            payload={"verdict": state.verdict},
        )

    async def _emit_artifacts(self, workspace: Path) -> None:
        source_identity = _git_source_identity(workspace)
        for artifact in discover_artifacts(workspace):
            if artifact.relative_path in self._artifacts:
                continue
            self._artifacts.add(artifact.relative_path)
            await self._emit(
                "ARTIFACT_DISCOVERED",
                "ARTIFACT",
                f"{artifact.display_name} recorded.",
                payload=self._artifact_payload(artifact, source_identity),
            )

    def _artifact_payload(
        self, artifact: NativeArtifact, source_identity: dict
    ) -> dict:
        payload: dict = {
            "artifact_class": artifact.artifact_class,
            "display_name": artifact.display_name,
            "relative_path": artifact.relative_path,
        }
        if artifact.path.is_file():
            try:
                payload["size_bytes"] = artifact.path.stat().st_size
                payload["content_hash"] = (
                    "sha256:" + hashlib.sha256(artifact.path.read_bytes()).hexdigest()
                )
            except OSError:
                pass
            payload["media_type"] = media_type_for(artifact.path)
        if source_identity:
            payload["source_identity"] = source_identity
        return payload

    async def _emit_stage(
        self,
        event_type: str,
        category: StageCategory,
        native_id: str | None = None,
    ) -> None:
        action = "started" if event_type == "STAGE_STARTED" else "completed"
        stage: EngineStage = make_stage(category, native_id)
        await self._emit(
            event_type,
            "STAGE",
            f"Stage {stage.display_label} {action}.",
            stage=stage,
        )

    async def _emit(
        self,
        event_type: str,
        category: str,
        summary: str,
        *,
        severity: EventSeverity = EventSeverity.INFO,
        stage: EngineStage | None = None,
        work_item_native_id: str | None = None,
        payload: dict | None = None,
    ) -> None:
        self._sequence += 1
        await self._hooks.on_event(
            EngineEvent(
                event_type=event_type,
                category=category,
                summary=summary,
                severity=severity,
                source_event_sequence=self._sequence,
                stage=stage,
                work_item_native_id=work_item_native_id,
                payload=payload or {},
            )
        )
