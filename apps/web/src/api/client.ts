const API_URL = (import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export function apiUrl(path: string): string {
  return `${API_URL}${path}`;
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(apiUrl(path), {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}
