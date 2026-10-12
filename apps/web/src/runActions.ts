import type { Attempt, Run } from "./api/client";

const STOPPABLE_STATES = new Set(["RUNNING", "WAITING_FOR_HUMAN"]);
const RESUMABLE_STATES = new Set(["STOPPED", "FAILED"]);

export function canRequestSafeStop(state: string): boolean {
  return STOPPABLE_STATES.has(state);
}

export function canResume(run: Run): boolean {
  return RESUMABLE_STATES.has(run.control_state) && run.recovery.resume_allowed;
}

export function blockedResumeReason(run: Run): string | null {
  if (canResume(run)) {
    return null;
  }
  if (!RESUMABLE_STATES.has(run.control_state)) {
    return null;
  }
  return run.recovery.reason ?? "Resume is not available for this Run.";
}

export function attemptLabel(attempt: Attempt): string {
  const state = attempt.state.charAt(0) + attempt.state.slice(1).toLowerCase();
  return attempt.terminal_reason
    ? `Attempt ${attempt.ordinal} — ${state} (${attempt.terminal_reason})`
    : `Attempt ${attempt.ordinal} — ${state}`;
}

export function failureLabel(run: Run): string | null {
  if (!run.failure) {
    return null;
  }
  const parts = [run.failure.code ?? run.failure.class ?? "ENGINE_FAILURE"];
  if (run.failure.recoverability) {
    parts.push(run.failure.recoverability);
  }
  return parts.join(" · ");
}
