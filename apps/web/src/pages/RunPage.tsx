import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { getRun } from "../api/client";
import { isTerminalState } from "../runState";

export function RunPage() {
  const { projectId = "", runId = "" } = useParams();
  const run = useQuery({
    queryKey: ["run", runId],
    queryFn: () => getRun(runId),
    refetchInterval: (query) =>
      query.state.data && isTerminalState(query.state.data.control_state) ? false : 1000,
  });

  return (
    <main>
      <p>
        <Link to={`/projects/${projectId}`}>Back to project</Link>
      </p>
      <h1>Run</h1>
      {run.isLoading && <p>Loading run...</p>}
      {run.isError && <p>Could not load the run.</p>}
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
    </main>
  );
}
