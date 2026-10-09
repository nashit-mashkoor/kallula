import type { EngineInstallation, Stage, WorkItemSummary } from "./api/client";
import type { RunEvent } from "./events";

export type StageState = "done" | "current" | "pending";

export type StageView = {
  category: string;
  label: string;
  order: number;
  state: StageState;
};

export function stageProgress(
  current: Stage | null,
  events: RunEvent[],
): StageView[] {
  const stages = new Map<string, StageView>();
  const add = (stage: Stage | null | undefined) => {
    if (!stage) {
      return;
    }
    if (!stages.has(stage.category)) {
      stages.set(stage.category, {
        category: stage.category,
        label: stage.display_label,
        order: stage.order,
        state: "pending",
      });
    }
  };
  add(current);
  for (const event of events) {
    if (event.event_type === "STAGE_STARTED" || event.event_type === "STAGE_COMPLETED") {
      add(event.stage ?? null);
    }
  }
  const completed = new Set(
    events
      .filter((event) => event.event_type === "STAGE_COMPLETED")
      .map((event) => event.stage?.category)
      .filter((category): category is string => Boolean(category)),
  );
  const started = events
    .filter(
      (event) =>
        event.event_type === "STAGE_STARTED" &&
        event.stage !== undefined &&
        event.stage !== null &&
        !completed.has(event.stage.category),
    )
    .map((event) => event.stage as Stage)
    .sort((left, right) => left.order - right.order);
  const currentCategory = current?.category ?? started.at(-1)?.category ?? null;
  return [...stages.values()]
    .sort((left, right) => left.order - right.order)
    .map((stage) => {
      if (completed.has(stage.category)) {
        return { ...stage, state: "done" as const };
      }
      if (stage.category === currentCategory) {
        return { ...stage, state: "current" as const };
      }
      return { ...stage, state: "pending" as const };
    });
}

export function workItemSummaryLabel(summary: WorkItemSummary | null): string | null {
  if (!summary || summary.total === 0) {
    return null;
  }
  const label = `${summary.completed} of ${summary.total} Work Items completed`;
  return summary.blocked > 0 ? `${label} — ${summary.blocked} blocked` : label;
}

export function workItemStateLabel(state: string): string {
  const labels: Record<string, string> = {
    PENDING: "Pending",
    ACTIVE: "Active",
    COMPLETED: "Completed",
    BLOCKED: "Blocked",
    SKIPPED: "Skipped",
    UNKNOWN: "Unknown",
  };
  return labels[state] ?? state;
}

export function shortRevision(revision: string): string {
  return revision.length > 7 ? revision.slice(0, 7) : revision;
}

export function engineIdentityLabel(
  installation: EngineInstallation | null,
): string | null {
  if (!installation) {
    return null;
  }
  return `${installation.engine_family} ${shortRevision(
    installation.engine_revision,
  )} — adapter ${installation.adapter_version}`;
}
