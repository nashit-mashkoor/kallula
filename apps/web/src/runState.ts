const TERMINAL_STATES = new Set(["COMPLETED", "FAILED", "STOPPED"]);

export function isTerminalState(state: string): boolean {
  return TERMINAL_STATES.has(state);
}
