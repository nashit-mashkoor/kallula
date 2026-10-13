import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import type { Interaction, InteractionResponseType } from "../api/client";
import { respondToInteraction } from "../api/client";
import {
  allowedResponseTypes,
  answerReceivedLabel,
  canSubmitResponse,
  isFinalConfirmation,
  responseLabel,
  responseRequiresAnswer,
} from "../interactions";

export function InterviewPanel({
  interaction,
  runState,
  onSubmitted,
}: {
  interaction: Interaction;
  runState: string;
  onSubmitted: () => void;
}) {
  const [answer, setAnswer] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const respond = useMutation({
    mutationFn: (type: InteractionResponseType) =>
      respondToInteraction(
        interaction.id,
        type,
        responseRequiresAnswer(type) ? answer : undefined,
      ),
    onSuccess: () => {
      setSubmitted(true);
      onSubmitted();
    },
    onError: () => onSubmitted(),
  });

  const final = isFinalConfirmation(interaction);
  const types = allowedResponseTypes(interaction);
  const answerTypes = types.filter(responseRequiresAnswer);
  const actionTypes = types.filter((type) => !responseRequiresAnswer(type));

  return (
    <section aria-label="Pending interaction">
      <h2>{final ? "Confirm project intent" : "Requirements interview"}</h2>
      {final ? (
        <p>Kallula understands the project as:</p>
      ) : (
        <p>Answer the question below to continue the same Run.</p>
      )}
      <blockquote>{interaction.prompt}</blockquote>

      {!final && interaction.recommendation && (
        <p>
          <strong>Engine recommendation</strong>
          <br />
          {interaction.recommendation}
        </p>
      )}

      {submitted ? (
        <p role="status">{answerReceivedLabel(runState)}</p>
      ) : (
        <>
          {answerTypes.length > 0 && (
            <p>
              <label>
                {final ? "What should change?" : "Your answer"}
                <textarea
                  value={answer}
                  onChange={(event) => setAnswer(event.target.value)}
                  disabled={respond.isPending}
                />
              </label>
              {answerTypes.map((type) => (
                <button
                  key={type}
                  onClick={() => respond.mutate(type)}
                  disabled={
                    respond.isPending ||
                    !canSubmitResponse(interaction, type, answer)
                  }
                >
                  {responseLabel(type)}
                </button>
              ))}
            </p>
          )}
          <p>
            {actionTypes.map((type) => (
              <button
                key={type}
                onClick={() => respond.mutate(type)}
                disabled={
                  respond.isPending ||
                  !canSubmitResponse(interaction, type, answer)
                }
              >
                {responseLabel(type)}
              </button>
            ))}
          </p>
          {respond.isError && <p role="alert">Could not submit the answer.</p>}
        </>
      )}
    </section>
  );
}
