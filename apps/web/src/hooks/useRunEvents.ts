import { useEffect, useState } from "react";

import { apiUrl } from "../api/client";
import type { RunEvent } from "../events";
import { mergeEvents } from "../events";

export type StreamStatus = "connecting" | "live" | "stale";

export function useRunEvents(runId: string) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [status, setStatus] = useState<StreamStatus>("connecting");

  useEffect(() => {
    setEvents([]);
    setStatus("connecting");
    const source = new EventSource(apiUrl(`/api/v1/runs/${runId}/events/stream`));
    source.addEventListener("open", () => setStatus("live"));
    source.addEventListener("error", () => setStatus("stale"));
    source.addEventListener("run_event", (message) => {
      const event = JSON.parse((message as MessageEvent).data) as RunEvent;
      setEvents((current) => mergeEvents(current, [event]));
    });
    return () => source.close();
  }, [runId]);

  return { events, status };
}
