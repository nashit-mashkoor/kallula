import { describe, expect, it } from "vitest";

import type { RunEvent } from "../../apps/web/src/events";
import { mergeEvents } from "../../apps/web/src/events";

function event(sequence: number, summary = `event ${sequence}`): RunEvent {
  return {
    id: `id-${sequence}`,
    run_id: "run-1",
    sequence,
    event_type: "RUN_STARTING",
    category: "RUN",
    severity: "INFO",
    summary,
    payload: {},
    recorded_at: "2026-10-07T00:00:00Z",
  };
}

describe("mergeEvents", () => {
  it("sorts events by sequence", () => {
    expect(mergeEvents([], [event(3), event(1), event(2)]).map((e) => e.sequence)).toEqual([
      1, 2, 3,
    ]);
  });

  it("deduplicates duplicate deliveries by sequence", () => {
    const merged = mergeEvents([event(1), event(2)], [event(2), event(3)]);
    expect(merged.map((e) => e.sequence)).toEqual([1, 2, 3]);
    expect(merged).toHaveLength(3);
  });

  it("keeps the newest representation of a repeated sequence", () => {
    const merged = mergeEvents([event(1, "old")], [event(1, "new")]);
    expect(merged[0].summary).toBe("new");
  });
});
