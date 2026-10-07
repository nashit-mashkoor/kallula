import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import { createProject } from "../api/client";

export function NewProject() {
  const [name, setName] = useState("");
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => createProject(name),
    onSuccess: (project) => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/projects/${project.id}`);
    },
  });

  return (
    <main>
      <h1>Create project</h1>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        <label>
          Display name
          <input value={name} onChange={(event) => setName(event.target.value)} required />
        </label>
        <button type="submit" disabled={mutation.isPending}>
          Create
        </button>
      </form>
      {mutation.isError && <p>Could not create the project.</p>}
    </main>
  );
}
