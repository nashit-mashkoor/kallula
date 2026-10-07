import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { Link, useParams } from "react-router";

import { createRun, getProject, listRuns } from "../api/client";
import { useAccountStream } from "../hooks/useAccountStream";

export function ProjectPage() {
  const { projectId = "" } = useParams();
  const [objective, setObjective] = useState("Build the initial product");
  const queryClient = useQueryClient();

  const refresh = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    void queryClient.invalidateQueries({ queryKey: ["runs", projectId] });
  }, [queryClient, projectId]);
  useAccountStream(refresh);

  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId),
  });
  const runs = useQuery({
    queryKey: ["runs", projectId],
    queryFn: () => listRuns(projectId),
  });
  const mutation = useMutation({
    mutationFn: () => createRun(projectId, objective),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["runs", projectId] });
    },
  });

  return (
    <main>
      <p>
        <Link to="/">Back to dashboard</Link>
      </p>
      <h1>{project.data?.display_name ?? "Project"}</h1>
      <p>Workspace: {project.data?.workspace_status ?? "unknown"}</p>

      <h2>New run</h2>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        <label>
          Objective
          <input value={objective} onChange={(event) => setObjective(event.target.value)} required />
        </label>
        <button type="submit" disabled={mutation.isPending}>
          Start run
        </button>
      </form>
      {mutation.isError && <p>Could not create the run.</p>}

      <h2>Runs</h2>
      <ul>
        {runs.data?.items.map((run) => (
          <li key={run.id}>
            <Link to={`/projects/${projectId}/runs/${run.id}`}>Run {run.ordinal}</Link> —{" "}
            {run.control_state}
          </li>
        ))}
        {runs.data?.items.length === 0 && <li>No runs yet.</li>}
      </ul>
    </main>
  );
}
