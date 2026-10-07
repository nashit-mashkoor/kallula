const API_URL = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export function apiUrl(path: string): string {
  return `${API_URL}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    headers: { Accept: "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
    },
    body: JSON.stringify(body),
  });
}

export type Project = {
  id: string;
  display_name: string;
  workspace_status: string;
  current_run_id: string | null;
  version: number;
};

export type Run = {
  id: string;
  project_id: string;
  ordinal: number;
  objective: string;
  control_state: string;
  version: number;
};

export function listProjects(): Promise<{ items: Project[] }> {
  return apiGet("/api/v1/projects");
}

export function createProject(displayName: string): Promise<Project> {
  return apiPost("/api/v1/projects", { display_name: displayName });
}

export function getProject(projectId: string): Promise<Project> {
  return apiGet(`/api/v1/projects/${projectId}`);
}

export function listRuns(projectId: string): Promise<{ items: Run[] }> {
  return apiGet(`/api/v1/projects/${projectId}/runs`);
}

export function createRun(projectId: string, objective: string): Promise<Run> {
  return apiPost(`/api/v1/projects/${projectId}/runs`, { objective });
}

export function getRun(runId: string): Promise<Run> {
  return apiGet(`/api/v1/runs/${runId}`);
}
