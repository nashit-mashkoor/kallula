import type { Interaction, InteractionResponseType, Run } from "./api/client";

export const WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN";
export const FINAL_INTENT_CONFIRMATION = "FINAL_INTENT_CONFIRMATION";

const RESPONSE_LABELS: Record<string, string> = {
  ANSWER: "Submit answer",
  USE_RECOMMENDATION: "Use the recommendation",
  CONFIRM: "Confirm intent",
  REQUEST_CHANGE: "Request a change",
  DELEGATE_REMAINING: "Let Kallula decide the remaining questions",
};

export function isWaitingForHuman(run: Run | null | undefined): boolean {
  return (
    run?.control_state === WAITING_FOR_HUMAN && Boolean(run.pending_interaction_id)
  );
}

export function isFinalConfirmation(interaction: Interaction): boolean {
  return interaction.kind === FINAL_INTENT_CONFIRMATION;
}

export function responseLabel(type: string): string {
  return RESPONSE_LABELS[type] ?? type;
}

export function responseRequiresAnswer(type: string): boolean {
  return type === "ANSWER" || type === "REQUEST_CHANGE";
}

export function allowedResponseTypes(
  interaction: Interaction,
): InteractionResponseType[] {
  return interaction.allowed_responses.filter(
    (type): type is InteractionResponseType => type in RESPONSE_LABELS,
  );
}

export function canSubmitResponse(
  interaction: Interaction,
  type: InteractionResponseType,
  answer: string,
): boolean {
  if (!allowedResponseTypes(interaction).includes(type)) {
    return false;
  }
  if (responseRequiresAnswer(type)) {
    return answer.trim().length > 0;
  }
  if (type === "USE_RECOMMENDATION") {
    return Boolean(interaction.recommendation);
  }
  return true;
}

export function answerReceivedLabel(controlState: string): string {
  return controlState === "QUEUED"
    ? "Answer received. Kallula is continuing the same Run."
    : "Answer received.";
}
