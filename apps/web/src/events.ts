export type RunEvent = {
  id: string;
  run_id: string;
  sequence: number;
  event_type: string;
  category: string;
  severity: string;
  summary: string;
  payload: Record<string, unknown>;
  recorded_at: string;
};

export function mergeEvents(existing: RunEvent[], incoming: RunEvent[]): RunEvent[] {
  const bySequence = new Map<number, RunEvent>();
  for (const event of existing) {
    bySequence.set(event.sequence, event);
  }
  for (const event of incoming) {
    bySequence.set(event.sequence, event);
  }
  return [...bySequence.values()].sort((left, right) => left.sequence - right.sequence);
}
