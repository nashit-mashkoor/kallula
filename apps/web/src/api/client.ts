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

export type Stage = {
  category: string;
  native_id: string | null;
  display_label: string;
  order: number;
};

export type WorkItemSummary = {
  completed: number;
  total: number;
  blocked: number;
};

export type Run = {
  id: string;
  project_id: string;
  ordinal: number;
  objective: string;
  control_state: string;
  stage: Stage | null;
  active_work_item_id: string | null;
  work_item_summary: WorkItemSummary | null;
  engine_installation_id: string | null;
  failure: {
    class: string | null;
    code: string | null;
    summary: string | null;
  } | null;
  version: number;
};

export type WorkItem = {
  id: string;
  run_id: string;
  engine_key: string;
  ordinal: number | null;
  title: string;
  description: string;
  acceptance_criteria: string[];
  state: string;
  blocker: string | null;
  related_commit: string | null;
  attempt_count: number;
};

export type Artifact = {
  id: string;
  project_id: string;
  run_id: string | null;
  artifact_class: string;
  display_name: string;
  media_type: string | null;
  size_bytes: number | null;
  content_hash: string | null;
  storage_kind: string;
  source_identity: { git_commit?: string };
};

export type EngineInstallation = {
  id: string;
  engine_family: string;
  engine_revision: string;
  adapter_version: string;
  status: string;
  default_for_new_runs: boolean;
};

export type RunConfiguration = {
  id: string;
  run_id: string;
  engine_installation_id: string | null;
  engine_installation: EngineInstallation | null;
  capability_manifest_hash: string | null;
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

export function getRunConfiguration(runId: string): Promise<RunConfiguration> {
  return apiGet(`/api/v1/runs/${runId}/configuration`);
}

export function listWorkItems(runId: string): Promise<{ items: WorkItem[] }> {
  return apiGet(`/api/v1/runs/${runId}/work-items`);
}

export function listArtifacts(runId: string): Promise<{ items: Artifact[] }> {
  return apiGet(`/api/v1/runs/${runId}/artifacts`);
}

export function artifactContentUrl(artifactId: string): string {
  return apiUrl(`/api/v1/artifacts/${artifactId}/content`);
}
