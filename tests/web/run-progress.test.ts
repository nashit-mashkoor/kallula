import { describe, expect, it } from "vitest";

import type { RunEvent } from "../../apps/web/src/events";
import {
  engineIdentityLabel,
  shortRevision,
  stageProgress,
  workItemStateLabel,
  workItemSummaryLabel,
} from "../../apps/web/src/runProgress";

function stageEvent(
  sequence: number,
  eventType: "STAGE_STARTED" | "STAGE_COMPLETED",
  category: string,
  label: string,
  order: number,
): RunEvent {
  return {
    id: `id-${sequence}`,
    run_id: "run-1",
    sequence,
    event_type: eventType,
    category: "STAGE",
    severity: "INFO",
    summary: `${label} event`,
    payload: {},
    recorded_at: "2026-10-09T00:00:00Z",
    stage: { category, native_id: null, display_label: label, order },
  };
}

describe("stageProgress", () => {
  it("marks completed and current stages from normalized events", () => {
    const events = [
      stageEvent(1, "STAGE_STARTED", "REQUIREMENTS", "Requirements", 1),
      stageEvent(2, "STAGE_COMPLETED", "REQUIREMENTS", "Requirements", 1),
      stageEvent(3, "STAGE_STARTED", "EXECUTION", "Execution", 4),
    ];

    const view = stageProgress(
      { category: "EXECUTION", native_id: null, display_label: "Execution", order: 4 },
      events,
    );

    expect(view.map((stage) => [stage.category, stage.state])).toEqual([
      ["REQUIREMENTS", "done"],
      ["EXECUTION", "current"],
    ]);
  });

  it("falls back to the latest started stage without a current stage", () => {
    const events = [stageEvent(1, "STAGE_STARTED", "SPECIFICATION", "Specification", 2)];

    expect(stageProgress(null, events)).toEqual([
      {
        category: "SPECIFICATION",
        label: "Specification",
        order: 2,
        state: "current",
      },
    ]);
  });

  it("returns nothing without stage data", () => {
    expect(stageProgress(null, [])).toEqual([]);
  });
});

describe("workItemSummaryLabel", () => {
  it("describes completion counts", () => {
    expect(workItemSummaryLabel({ completed: 3, total: 7, blocked: 0 })).toBe(
      "3 of 7 Work Items completed",
    );
  });

  it("mentions blocked items", () => {
    expect(workItemSummaryLabel({ completed: 3, total: 7, blocked: 2 })).toBe(
      "3 of 7 Work Items completed — 2 blocked",
    );
  });

  it("is absent before work items exist", () => {
    expect(workItemSummaryLabel(null)).toBeNull();
    expect(workItemSummaryLabel({ completed: 0, total: 0, blocked: 0 })).toBeNull();
  });
});

describe("workItemStateLabel", () => {
  it("maps normalized states", () => {
    expect(workItemStateLabel("BLOCKED")).toBe("Blocked");
    expect(workItemStateLabel("COMPLETED")).toBe("Completed");
    expect(workItemStateLabel("FUTURE_STATE")).toBe("FUTURE_STATE");
  });
});

describe("engineIdentityLabel", () => {
  it("labels the installed engine", () => {
    expect(
      engineIdentityLabel({
        id: "installation-1",
        engine_family: "SIESTA",
        engine_revision: "20b149e0734b09730dfd22803d2695776fcf84b8",
        adapter_version: "0.1.0",
        status: "SUPPORTED",
        default_for_new_runs: true,
      }),
    ).toBe("SIESTA 20b149e — adapter 0.1.0");
  });

  it("is absent without an installation", () => {
    expect(engineIdentityLabel(null)).toBeNull();
  });
});

describe("shortRevision", () => {
  it("truncates long revisions", () => {
    expect(shortRevision("20b149e0734b0973")).toBe("20b149e");
    expect(shortRevision("abc123")).toBe("abc123");
  });
});
