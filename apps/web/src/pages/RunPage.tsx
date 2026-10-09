import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, useParams } from "react-router";

import {
  artifactContentUrl,
  getRun,
  getRunConfiguration,
  listArtifacts,
  listWorkItems,
} from "../api/client";
import { useRunEvents } from "../hooks/useRunEvents";
import {
  engineIdentityLabel,
  stageProgress,
  workItemStateLabel,
  workItemSummaryLabel,
} from "../runProgress";
import { isTerminalState } from "../runState";

export function RunPage() {
  const { projectId = "", runId = "" } = useParams();
  const queryClient = useQueryClient();
  const run = useQuery({ queryKey: ["run", runId], queryFn: () => getRun(runId) });
  const workItems = useQuery({
    queryKey: ["work-items", runId],
    queryFn: () => listWorkItems(runId),
  });
  const artifacts = useQuery({
    queryKey: ["artifacts", runId],
    queryFn: () => listArtifacts(runId),
  });
  const configuration = useQuery({
    queryKey: ["run-configuration", runId],
    queryFn: () => getRunConfiguration(runId),
  });
  const { events, status } = useRunEvents(runId);

  useEffect(() => {
    if (events.length > 0) {
      void queryClient.invalidateQueries({ queryKey: ["run", runId] });
      void queryClient.invalidateQueries({ queryKey: ["work-items", runId] });
      void queryClient.invalidateQueries({ queryKey: ["artifacts", runId] });
    }
  }, [events.length, queryClient, runId]);

  const terminal = run.data ? isTerminalState(run.data.control_state) : false;
  const stages = stageProgress(run.data?.stage ?? null, events);
  const summary = workItemSummaryLabel(run.data?.work_item_summary ?? null);
  const installation = configuration.data?.engine_installation ?? null;
  const identity = engineIdentityLabel(installation);

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
          <dt>Stage</dt>
          <dd>{run.data.stage?.display_label ?? "Not started"}</dd>
          <dt>Ordinal</dt>
          <dd>{run.data.ordinal}</dd>
        </dl>
      )}
      {run.data?.failure && (
        <p role="alert">
          Run failed: {run.data.failure.summary ?? run.data.failure.code ?? "unknown reason"}
        </p>
      )}

      {stages.length > 0 && (
        <>
          <h2>Stages</h2>
          <ol>
            {stages.map((stage) => (
              <li key={stage.category}>
                {stage.state === "done" ? "✓" : stage.state === "current" ? "●" : "○"}{" "}
                {stage.label}
              </li>
            ))}
          </ol>
        </>
      )}

      <h2>Progress</h2>
      <p>{summary ?? "No work items yet."}</p>

      <h2>Work Items</h2>
      <ul>
        {workItems.data?.items.map((item) => (
          <li key={item.id}>
            {item.ordinal !== null ? `#${item.ordinal} ` : ""}
            {item.title} — {workItemStateLabel(item.state)}
            {item.blocker ? ` (${item.blocker})` : ""}
          </li>
        ))}
        {workItems.data?.items.length === 0 && <li>No work items yet.</li>}
      </ul>

      <h2>Artifacts</h2>
      <ul>
        {artifacts.data?.items.map((artifact) => (
          <li key={artifact.id}>
            <a href={artifactContentUrl(artifact.id)} target="_blank" rel="noreferrer">
              {artifact.display_name}
            </a>
          </li>
        ))}
        {artifacts.data?.items.length === 0 && <li>No artifacts yet.</li>}
      </ul>

      <h2>Configuration</h2>
      {identity ? (
        <dl>
          <dt>Engine</dt>
          <dd>{identity}</dd>
          <dt>Installation status</dt>
          <dd>{installation?.status}</dd>
        </dl>
      ) : (
        <p>Engine identity is not available.</p>
      )}

      <h2>Activity</h2>
      <ul>
        {events.map((event) => (
          <li key={event.sequence}>
            #{event.sequence} {event.stage ? `${event.stage.display_label}: ` : ""}
            {event.event_type} — {event.summary}
          </li>
        ))}
        {events.length === 0 && <li>Waiting for events...</li>}
      </ul>
    </main>
  );
}
