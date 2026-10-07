import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { Link } from "react-router";

import { listProjects } from "../api/client";
import { useAccountStream } from "../hooks/useAccountStream";

export function Dashboard() {
  const queryClient = useQueryClient();
  const refresh = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["projects"] });
  }, [queryClient]);
  useAccountStream(refresh);

  const projects = useQuery({ queryKey: ["projects"], queryFn: listProjects });

  return (
    <main>
      <h1>Kallula</h1>
      <p>
        <Link to="/projects/new">Create project</Link>
      </p>
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
