import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, useParams } from "react-router";

import { getRun } from "../api/client";
import { useRunEvents } from "../hooks/useRunEvents";
import { isTerminalState } from "../runState";

export function RunPage() {
  const { projectId = "", runId = "" } = useParams();
  const queryClient = useQueryClient();
  const run = useQuery({ queryKey: ["run", runId], queryFn: () => getRun(runId) });
  const { events, status } = useRunEvents(runId);

  useEffect(() => {
    if (events.length > 0) {
      void queryClient.invalidateQueries({ queryKey: ["run", runId] });
    }
  }, [events.length, queryClient, runId]);

  const terminal = run.data ? isTerminalState(run.data.control_state) : false;

  return (
    <main>
      <p>
        <Link to={`/projects/${projectId}`}>Back to project</Link>
      </p>
      <h1>Run</h1>
      <p>
        Stream:{" "}
        {status === "live" ? "live" : status === "stale" ? "reconnecting..." : "connecting..."}
        {terminal ? " — finished" : ""}
      </p>
      {run.data && (
        <dl>
          <dt>Objective</dt>
          <dd>{run.data.objective}</dd>
          <dt>State</dt>
          <dd>{run.data.control_state}</dd>
          <dt>Ordinal</dt>
          <dd>{run.data.ordinal}</dd>
        </dl>
      )}
      <h2>Activity</h2>
      <ul>
        {events.map((event) => (
          <li key={event.sequence}>
            #{event.sequence} {event.event_type} — {event.summary}
          </li>
        ))}
        {events.length === 0 && <li>Waiting for events...</li>}
      </ul>
    </main>
  );
}
