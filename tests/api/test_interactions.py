import asyncio

from helpers import (
    fetch_events,
    seed_interaction,
    seed_run,
    set_run_state,
)
from sqlalchemy import select

from domain.states import (
    InteractionKind,
    InteractionResponseType,
    InteractionState,
    RunControlState,
)
from persistence.db import create_db_engine, create_session_factory
from persistence.models import InteractionResponse, PendingInteraction, Run


def fetch_stored(database_url: str, run_id: str):
    async def scenario():
        engine = create_db_engine(database_url)
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one_or_none()
                responses = (
                    (
                        await session.execute(
                            select(InteractionResponse).where(
                                InteractionResponse.run_id == run_id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                interactions = (
                    (
                        await session.execute(
                            select(PendingInteraction).where(
                                PendingInteraction.run_id == run_id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                return run, list(responses), list(interactions)
        finally:
            await engine.dispose()

    return asyncio.run(scenario())


def test_list_open_interactions(client, database_url):
    run_id = seed_run(database_url)
    interaction_id = seed_interaction(database_url, run_id)

    response = client.get("/api/v1/interactions?status=OPEN")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["id"] for item in items] == [interaction_id]
    item = items[0]
    assert item["run_id"] == run_id
    assert item["kind"] == "QUESTION"
    assert item["status"] == "OPEN"
    assert item["prompt"] == "Which UI?"
    assert item["recommendation"] == "menu bar"
    assert item["allowed_responses"] == [
        "ANSWER",
        "USE_RECOMMENDATION",
        "DELEGATE_REMAINING",
    ]
    assert "engine_interaction_token" not in item


def test_get_interaction_and_unknown_status(client, database_url):
    run_id = seed_run(database_url)
    interaction_id = seed_interaction(database_url, run_id)

    response = client.get(f"/api/v1/interactions/{interaction_id}")

    assert response.status_code == 200
    assert response.json()["id"] == interaction_id
    assert client.get("/api/v1/interactions/unknown").status_code == 404
    assert client.get("/api/v1/interactions?status=NOPE").status_code == 422


def test_answer_question_queues_run_and_records_response(client, database_url):
    run_id = seed_run(database_url)
    interaction_id = seed_interaction(database_url, run_id)

    response = client.post(
        f"/api/v1/interactions/{interaction_id}/commands/respond",
        json={"response_type": "ANSWER", "answer": "menu bar please"},
        headers={"Idempotency-Key": "answer-1"},
    )

    assert response.status_code == 202
    command = response.json()
    assert command["command_type"] == "RESPOND_INTERACTION"
    assert command["state"] == "APPLIED"
    assert command["result_refs"]["interaction_response_id"]

    run, responses, interactions = fetch_stored(database_url, run_id)
    assert run.control_state is RunControlState.QUEUED
    assert run.pending_interaction_id is None
    assert interactions[0].status is InteractionState.ANSWERED
    assert interactions[0].resolved_at is not None
    assert responses[0].answer_text == "menu bar please"
    assert responses[0].response_type is InteractionResponseType.ANSWER

    events = fetch_events(database_url, run_id)
    assert [event[0] for event in events] == ["INTERACTION_RESOLVED", "RUN_QUEUED"]

    run_response = client.get(f"/api/v1/runs/{run_id}").json()
    assert run_response["control_state"] == "QUEUED"
    assert run_response["pending_interaction_id"] is None


def test_duplicate_retry_returns_original_command(client, database_url):
    run_id = seed_run(database_url)
    interaction_id = seed_interaction(database_url, run_id)
    payload = {"response_type": "ANSWER", "answer": "menu bar"}
    headers = {"Idempotency-Key": "answer-1"}

    first = client.post(
        f"/api/v1/interactions/{interaction_id}/commands/respond",
        json=payload,
        headers=headers,
    )
    second = client.post(
        f"/api/v1/interactions/{interaction_id}/commands/respond",
        json=payload,
        headers=headers,
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["id"] == first.json()["id"]
    _, responses, _ = fetch_stored(database_url, run_id)
    assert len(responses) == 1


def test_second_different_response_conflicts(client, database_url):
    run_id = seed_run(database_url)
    interaction_id = seed_interaction(database_url, run_id)
    client.post(
        f"/api/v1/interactions/{interaction_id}/commands/respond",
        json={"response_type": "ANSWER", "answer": "menu bar"},
        headers={"Idempotency-Key": "answer-1"},
    )

    second = client.post(
        f"/api/v1/interactions/{interaction_id}/commands/respond",
        json={"response_type": "ANSWER", "answer": "terminal"},
        headers={"Idempotency-Key": "answer-2"},
    )

    assert second.status_code == 409
    assert second.json()["code"] == "INTERACTION_ALREADY_RESOLVED"
    _, responses, _ = fetch_stored(database_url, run_id)
    assert len(responses) == 1


def test_response_type_must_match_kind(client, database_url):
    run_id = seed_run(database_url)
    interaction_id = seed_interaction(
        database_url, run_id, kind=InteractionKind.FINAL_INTENT_CONFIRMATION
    )

    response = client.post(
        f"/api/v1/interactions/{interaction_id}/commands/respond",
        json={"response_type": "ANSWER", "answer": "no"},
        headers={"Idempotency-Key": "bad-kind"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    run, _, _ = fetch_stored(database_url, run_id)
    assert run.control_state is RunControlState.WAITING_FOR_HUMAN


def test_answer_requires_text(client, database_url):
    run_id = seed_run(database_url)
    interaction_id = seed_interaction(database_url, run_id)

    response = client.post(
        f"/api/v1/interactions/{interaction_id}/commands/respond",
        json={"response_type": "ANSWER"},
        headers={"Idempotency-Key": "empty-answer"},
    )

    assert response.status_code == 422


def test_confirm_final_intent(client, database_url):
    run_id = seed_run(database_url)
    interaction_id = seed_interaction(
        database_url,
        run_id,
        kind=InteractionKind.FINAL_INTENT_CONFIRMATION,
        prompt="A menu-bar pomodoro timer.",
        recommendation=None,
    )

    response = client.post(
        f"/api/v1/interactions/{interaction_id}/commands/respond",
        json={"response_type": "CONFIRM"},
        headers={"Idempotency-Key": "confirm-1"},
    )

    assert response.status_code == 202
    run, responses, interactions = fetch_stored(database_url, run_id)
    assert run.control_state is RunControlState.QUEUED
    assert interactions[0].status is InteractionState.ANSWERED
    assert responses[0].response_type is InteractionResponseType.CONFIRM
    assert responses[0].answer_text is None


def test_delegate_remaining_marks_delegated(client, database_url):
    run_id = seed_run(database_url)
    interaction_id = seed_interaction(database_url, run_id)

    response = client.post(
        f"/api/v1/interactions/{interaction_id}/commands/respond",
        json={"response_type": "DELEGATE_REMAINING"},
        headers={"Idempotency-Key": "delegate-1"},
    )

    assert response.status_code == 202
    _, _, interactions = fetch_stored(database_url, run_id)
    assert interactions[0].status is InteractionState.DELEGATED


def test_use_recommendation_materializes_the_recommendation(client, database_url):
    run_id = seed_run(database_url)
    interaction_id = seed_interaction(database_url, run_id)

    response = client.post(
        f"/api/v1/interactions/{interaction_id}/commands/respond",
        json={"response_type": "USE_RECOMMENDATION"},
        headers={"Idempotency-Key": "recommend-1"},
    )

    assert response.status_code == 202
    _, responses, _ = fetch_stored(database_url, run_id)
    assert responses[0].answer_text == "menu bar"


def test_respond_requires_waiting_run(client, database_url):
    run_id = seed_run(database_url)
    interaction_id = seed_interaction(database_url, run_id)
    set_run_state(database_url, run_id, RunControlState.STOPPED)

    response = client.post(
        f"/api/v1/interactions/{interaction_id}/commands/respond",
        json={"response_type": "ANSWER", "answer": "menu bar"},
        headers={"Idempotency-Key": "stopped-1"},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "RUN_STATE_CONFLICT"
