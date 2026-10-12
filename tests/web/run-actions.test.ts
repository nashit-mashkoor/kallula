import { describe, expect, it } from "vitest";

import type { Attempt, Run } from "../../apps/web/src/api/client";
import {
  attemptLabel,
  blockedResumeReason,
  canRequestSafeStop,
  canResume,
  failureLabel,
} from "../../apps/web/src/runActions";

function run(overrides: Partial<Run> = {}): Run {
  return {
    id: "run-1",
    project_id: "project-1",
    ordinal: 1,
    objective: "Build it",
    control_state: "RUNNING",
    stage: null,
    active_work_item_id: null,
    work_item_summary: null,
    engine_installation_id: null,
    recovery: { resume_allowed: false, reason: null },
    failure: null,
    version: 1,
    ...overrides,
  };
}

function attempt(overrides: Partial<Attempt> = {}): Attempt {
  return {
    id: "attempt-1",
    run_id: "run-1",
    ordinal: 1,
    state: "EXITED",
    terminal_reason: "SAFE_STOP",
    created_at: "2026-10-10T00:00:00Z",
    started_at: null,
    ended_at: null,
    ...overrides,
  };
}

describe("canRequestSafeStop", () => {
  it("allows active runs only", () => {
    expect(canRequestSafeStop("RUNNING")).toBe(true);
    expect(canRequestSafeStop("WAITING_FOR_HUMAN")).toBe(true);
    expect(canRequestSafeStop("STOP_REQUESTED")).toBe(false);
    expect(canRequestSafeStop("COMPLETED")).toBe(false);
  });
});

describe("canResume", () => {
  it("requires a resumable state and server allowance", () => {
    expect(
      canResume(
        run({
          control_state: "STOPPED",
          recovery: { resume_allowed: true, reason: null },
        }),
      ),
    ).toBe(true);
    expect(canResume(run({ control_state: "STOPPED" }))).toBe(false);
    expect(
      canResume(
        run({
          control_state: "RUNNING",
          recovery: { resume_allowed: true, reason: null },
        }),
      ),
    ).toBe(false);
  });
});

describe("blockedResumeReason", () => {
  it("explains blocked resume for terminal runs", () => {
    expect(
      blockedResumeReason(
        run({
          control_state: "FAILED",
          recovery: {
            resume_allowed: false,
            reason: "This failure is not automatically resumable.",
          },
        }),
      ),
    ).toBe("This failure is not automatically resumable.");
  });

  it("is absent when resume is available or the run is active", () => {
    expect(
      blockedResumeReason(
        run({
          control_state: "STOPPED",
          recovery: { resume_allowed: true, reason: null },
        }),
      ),
    ).toBeNull();
    expect(blockedResumeReason(run({ control_state: "RUNNING" }))).toBeNull();
  });
});

describe("attemptLabel", () => {
  it("labels attempts with state and terminal reason", () => {
    expect(attemptLabel(attempt())).toBe("Attempt 1 — Exited (SAFE_STOP)");
    expect(attemptLabel(attempt({ ordinal: 2, state: "LOST", terminal_reason: null }))).toBe(
      "Attempt 2 — Lost",
    );
  });
});

describe("failureLabel", () => {
  it("summarizes failure code and recoverability", () => {
    expect(
      failureLabel(
        run({
          failure: {
            class: "ENGINE_FAILURE",
            code: "ENGINE_UNVERIFIED",
            summary: "Verification did not pass.",
            recoverability: "RESUMABLE",
          },
        }),
      ),
    ).toBe("ENGINE_UNVERIFIED · RESUMABLE");
  });

  it("is absent without a failure", () => {
    expect(failureLabel(run())).toBeNull();
  });
});
