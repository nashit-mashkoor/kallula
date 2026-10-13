import { describe, expect, it } from "vitest";

import { isActiveRunState, isTerminalState } from "../../apps/web/src/runState";

describe("isTerminalState", () => {
  it("recognizes terminal states", () => {
    expect(isTerminalState("COMPLETED")).toBe(true);
    expect(isTerminalState("FAILED")).toBe(true);
    expect(isTerminalState("STOPPED")).toBe(true);
  });

  it("treats active states as non-terminal", () => {
    expect(isTerminalState("QUEUED")).toBe(false);
    expect(isTerminalState("RUNNING")).toBe(false);
  });
});

describe("isActiveRunState", () => {
  it("keeps a Project busy until its Run is terminal", () => {
    expect(isActiveRunState("QUEUED")).toBe(true);
    expect(isActiveRunState("RUNNING")).toBe(true);
    expect(isActiveRunState("WAITING_FOR_HUMAN")).toBe(true);
    expect(isActiveRunState("STOP_REQUESTED")).toBe(true);
    expect(isActiveRunState("STOPPED")).toBe(false);
    expect(isActiveRunState("FAILED")).toBe(false);
    expect(isActiveRunState("COMPLETED")).toBe(false);
  });
});
