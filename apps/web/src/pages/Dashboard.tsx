import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { Link } from "react-router";

import { getRun, listOpenInteractions, listProjects } from "../api/client";
import { useAccountStream } from "../hooks/useAccountStream";

export function Dashboard() {
  const queryClient = useQueryClient();
  const refresh = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["projects"] });
    void queryClient.invalidateQueries({ queryKey: ["interactions", "OPEN"] });
    void queryClient.invalidateQueries({ queryKey: ["run"] });
  }, [queryClient]);
  useAccountStream(refresh);

  const projects = useQuery({ queryKey: ["projects"], queryFn: listProjects });
  const interactions = useQuery({
    queryKey: ["interactions", "OPEN"],
    queryFn: listOpenInteractions,
  });
  const waiting = interactions.data?.items ?? [];
  const waitingRuns = useQueries({
    queries: waiting.map((interaction) => ({
      queryKey: ["run", interaction.run_id],
      queryFn: () => getRun(interaction.run_id),
    })),
  });

  return (
    <main>
      <h1>Kallula</h1>
      <p>
        <Link to="/projects/new">Create project</Link>
      </p>
      {waiting.length > 0 && (
        <section aria-label="Waiting for your input">
          <h2>Waiting for your input</h2>
          <ul>
            {waiting.map((interaction, index) => {
              const projectId = waitingRuns[index]?.data?.project_id;
              return (
                <li key={interaction.id}>
                  {projectId ? (
                    <Link to={`/projects/${projectId}/runs/${interaction.run_id}`}>
                      Answer now: {interaction.prompt}
                    </Link>
                  ) : (
                    interaction.prompt
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}
      {projects.isLoading && <p>Loading projects...</p>}
      {projects.isError && <p>Could not load projects.</p>}
      {projects.data && (
        <ul>
          {projects.data.items.map((project) => (
            <li key={project.id}>
              <Link to={`/projects/${project.id}`}>{project.display_name}</Link> —{" "}
              {project.workspace_status}
            </li>
          ))}
          {projects.data.items.length === 0 && <li>No projects yet.</li>}
        </ul>
      )}
    </main>
  );
}
