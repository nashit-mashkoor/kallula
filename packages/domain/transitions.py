from domain.states import AttemptState, RunControlState


class InvalidTransitionError(RuntimeError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"Invalid transition: {current} -> {target}")


RUN_TRANSITIONS: dict[RunControlState, frozenset[RunControlState]] = {
    RunControlState.QUEUED: frozenset(
        {RunControlState.STARTING, RunControlState.STOPPED, RunControlState.FAILED}
    ),
    RunControlState.STARTING: frozenset(
        {
            RunControlState.RUNNING,
            RunControlState.FAILED,
            RunControlState.STOP_REQUESTED,
            RunControlState.STOPPED,
        }
    ),
    RunControlState.RUNNING: frozenset(
        {
            RunControlState.WAITING_FOR_HUMAN,
            RunControlState.STOP_REQUESTED,
            RunControlState.STOPPED,
            RunControlState.FAILED,
            RunControlState.COMPLETED,
        }
    ),
    RunControlState.WAITING_FOR_HUMAN: frozenset(
        {
            RunControlState.QUEUED,
            RunControlState.STOP_REQUESTED,
            RunControlState.STOPPED,
            RunControlState.FAILED,
        }
    ),
    RunControlState.STOP_REQUESTED: frozenset(
        {RunControlState.STOPPED, RunControlState.COMPLETED, RunControlState.FAILED}
    ),
    RunControlState.STOPPED: frozenset({RunControlState.QUEUED}),
    RunControlState.FAILED: frozenset({RunControlState.QUEUED}),
    RunControlState.COMPLETED: frozenset(),
}

ATTEMPT_TRANSITIONS: dict[AttemptState, frozenset[AttemptState]] = {
    AttemptState.ALLOCATED: frozenset({AttemptState.STARTING, AttemptState.LOST}),
    AttemptState.STARTING: frozenset(
        {AttemptState.ACTIVE, AttemptState.EXITED, AttemptState.LOST}
    ),
    AttemptState.ACTIVE: frozenset(
        {AttemptState.SUSPENDED, AttemptState.EXITED, AttemptState.LOST}
    ),
    AttemptState.SUSPENDED: frozenset(
        {AttemptState.ACTIVE, AttemptState.EXITED, AttemptState.LOST}
    ),
    AttemptState.EXITED: frozenset(),
    AttemptState.LOST: frozenset(),
}


def next_run_state(
    current: RunControlState, target: RunControlState
) -> RunControlState:
    if target not in RUN_TRANSITIONS[current]:
        raise InvalidTransitionError(current.value, target.value)
    return target


def next_attempt_state(current: AttemptState, target: AttemptState) -> AttemptState:
    if target not in ATTEMPT_TRANSITIONS[current]:
        raise InvalidTransitionError(current.value, target.value)
    return target


def can_transition_run(current: RunControlState, target: RunControlState) -> bool:
    return target in RUN_TRANSITIONS[current]


def can_transition_attempt(current: AttemptState, target: AttemptState) -> bool:
    return target in ATTEMPT_TRANSITIONS[current]
