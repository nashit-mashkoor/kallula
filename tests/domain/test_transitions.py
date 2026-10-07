import pytest

from domain.states import AttemptState, RunControlState
from domain.transitions import (
    InvalidTransitionError,
    can_transition_run,
    next_attempt_state,
    next_run_state,
)


def test_run_happy_path():
    state = RunControlState.QUEUED
    state = next_run_state(state, RunControlState.STARTING)
    state = next_run_state(state, RunControlState.RUNNING)
    state = next_run_state(state, RunControlState.COMPLETED)

    assert state is RunControlState.COMPLETED


def test_completed_is_terminal():
    assert (
        can_transition_run(RunControlState.COMPLETED, RunControlState.RUNNING) is False
    )
    with pytest.raises(InvalidTransitionError):
        next_run_state(RunControlState.COMPLETED, RunControlState.RUNNING)


def test_cannot_skip_starting():
    with pytest.raises(InvalidTransitionError):
        next_run_state(RunControlState.QUEUED, RunControlState.RUNNING)


def test_stopped_and_failed_can_resume():
    assert (
        next_run_state(RunControlState.STOPPED, RunControlState.QUEUED)
        is RunControlState.QUEUED
    )
    assert (
        next_run_state(RunControlState.FAILED, RunControlState.QUEUED)
        is RunControlState.QUEUED
    )


def test_attempt_transitions():
    state = next_attempt_state(AttemptState.ALLOCATED, AttemptState.STARTING)
    state = next_attempt_state(state, AttemptState.ACTIVE)
    state = next_attempt_state(state, AttemptState.EXITED)

    assert state is AttemptState.EXITED
    with pytest.raises(InvalidTransitionError):
        next_attempt_state(AttemptState.EXITED, AttemptState.ACTIVE)
