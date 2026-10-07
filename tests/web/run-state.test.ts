import { describe, expect, it } from "vitest";

import { isTerminalState } from "../../apps/web/src/runState";

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
