import { describe, expect, it } from "vitest";

import type { Interaction, Run } from "../../apps/web/src/api/client";
import {
  allowedResponseTypes,
  answerReceivedLabel,
  canSubmitResponse,
  isFinalConfirmation,
  isWaitingForHuman,
  responseLabel,
  responseRequiresAnswer,
} from "../../apps/web/src/interactions";

function run(overrides: Partial<Run> = {}): Run {
  return {
    id: "run-1",
    project_id: "project-1",
    ordinal: 1,
    objective: "Build it",
    control_state: "RUNNING",
    stage: null,
    active_work_item_id: null,
    work_item_summary: null,
    engine_installation_id: null,
    pending_interaction_id: null,
    recovery: { resume_allowed: false, reason: null },
    failure: null,
    version: 1,
    ...overrides,
  };
}

function interaction(overrides: Partial<Interaction> = {}): Interaction {
  return {
    id: "interaction-1",
    run_id: "run-1",
    attempt_id: "attempt-1",
    kind: "QUESTION",
    status: "OPEN",
    title: "Requirements question",
    prompt: "Which UI?",
    recommendation: "menu bar",
    context: { accepted_turns: [] },
    allowed_responses: ["ANSWER", "USE_RECOMMENDATION", "DELEGATE_REMAINING"],
    created_at: "2026-10-12T00:00:00Z",
    resolved_at: null,
    version: 1,
    ...overrides,
  };
}

describe("isWaitingForHuman", () => {
  it("requires the waiting state and a pending interaction", () => {
    expect(
      isWaitingForHuman(
        run({
          control_state: "WAITING_FOR_HUMAN",
          pending_interaction_id: "interaction-1",
        }),
      ),
    ).toBe(true);
    expect(
      isWaitingForHuman(run({ control_state: "WAITING_FOR_HUMAN" })),
    ).toBe(false);
    expect(
      isWaitingForHuman(
        run({ control_state: "RUNNING", pending_interaction_id: "i-1" }),
      ),
    ).toBe(false);
    expect(isWaitingForHuman(null)).toBe(false);
  });
});

describe("interaction kinds and responses", () => {
  it("recognizes the final intent confirmation", () => {
    expect(isFinalConfirmation(interaction())).toBe(false);
    expect(
      isFinalConfirmation(interaction({ kind: "FINAL_INTENT_CONFIRMATION" })),
    ).toBe(true);
  });

  it("labels every response type", () => {
    expect(responseLabel("ANSWER")).toBe("Submit answer");
    expect(responseLabel("USE_RECOMMENDATION")).toBe("Use the recommendation");
    expect(responseLabel("CONFIRM")).toBe("Confirm intent");
    expect(responseLabel("REQUEST_CHANGE")).toBe("Request a change");
    expect(responseLabel("DELEGATE_REMAINING")).toBe(
      "Let Kallula decide the remaining questions",
    );
  });

  it("requires text only for answer-shaped responses", () => {
    expect(responseRequiresAnswer("ANSWER")).toBe(true);
    expect(responseRequiresAnswer("REQUEST_CHANGE")).toBe(true);
    expect(responseRequiresAnswer("CONFIRM")).toBe(false);
    expect(responseRequiresAnswer("USE_RECOMMENDATION")).toBe(false);
    expect(responseRequiresAnswer("DELEGATE_REMAINING")).toBe(false);
  });

  it("uses the server-provided allowed responses", () => {
    const confirm = interaction({
      kind: "FINAL_INTENT_CONFIRMATION",
      allowed_responses: ["CONFIRM", "REQUEST_CHANGE", "NONSENSE"],
    });
    expect(allowedResponseTypes(confirm)).toEqual(["CONFIRM", "REQUEST_CHANGE"]);
  });
});

describe("canSubmitResponse", () => {
  it("requires a non-empty answer for ANSWER", () => {
    const question = interaction();
    expect(canSubmitResponse(question, "ANSWER", "")).toBe(false);
    expect(canSubmitResponse(question, "ANSWER", "   ")).toBe(false);
    expect(canSubmitResponse(question, "ANSWER", "terminal")).toBe(true);
  });

  it("allows the recommendation only when one exists", () => {
    expect(
      canSubmitResponse(interaction(), "USE_RECOMMENDATION", ""),
    ).toBe(true);
    expect(
      canSubmitResponse(
        interaction({ recommendation: null }),
        "USE_RECOMMENDATION",
        "",
      ),
    ).toBe(false);
  });

  it("allows confirm and delegate without text", () => {
    const confirm = interaction({
      kind: "FINAL_INTENT_CONFIRMATION",
      allowed_responses: ["CONFIRM", "REQUEST_CHANGE"],
    });
    expect(canSubmitResponse(confirm, "CONFIRM", "")).toBe(true);
    expect(canSubmitResponse(confirm, "REQUEST_CHANGE", "")).toBe(false);
    expect(canSubmitResponse(confirm, "REQUEST_CHANGE", "also expenses")).toBe(
      true,
    );
    expect(canSubmitResponse(confirm, "DELEGATE_REMAINING", "")).toBe(false);
  });
});

describe("answerReceivedLabel", () => {
  it("says the run continues truthfully", () => {
    expect(answerReceivedLabel("QUEUED")).toBe(
      "Answer received. Kallula is continuing the same Run.",
    );
    expect(answerReceivedLabel("RUNNING")).toBe("Answer received.");
  });
});
