import asyncio

import pytest

from api.idempotency import (
    IdempotencyConflictError,
    replay,
    request_hash,
    store,
)
from persistence.db import create_db_engine, create_session_factory
from persistence.models import Principal


def test_request_hash_is_order_independent():
    assert request_hash({"b": 1, "a": 2}) == request_hash({"a": 2, "b": 1})
    assert request_hash({"a": 2}) != request_hash({"a": 3})


def test_replay_returns_stored_response_and_rejects_reuse(database_url):
    async def scenario():
        engine = create_db_engine(database_url)
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                session.add(
                    Principal(
                        id="dev-principal",
                        auth_provider="development",
                        auth_subject="dev-principal",
                        display_name="Development User",
                    )
                )
                await store(
                    session,
                    principal_id="dev-principal",
                    method="POST",
                    canonical_path="/api/v1/projects",
                    idempotency_key="key-1",
                    request_hash_value="hash-1",
                    status=201,
                    resource_ref="project-1",
                    snapshot={"id": "project-1"},
                )
                await session.commit()

            async with factory() as session:
                result = await replay(
                    session,
                    principal_id="dev-principal",
                    method="POST",
                    canonical_path="/api/v1/projects",
                    idempotency_key="key-1",
                    request_hash_value="hash-1",
                )
                assert result is not None
                assert result.status == 201
                assert result.resource_ref == "project-1"
                assert result.snapshot == {"id": "project-1"}

                missing = await replay(
                    session,
                    principal_id="dev-principal",
                    method="POST",
                    canonical_path="/api/v1/other",
                    idempotency_key="key-1",
                    request_hash_value="hash-1",
                )
                assert missing is None

                with pytest.raises(IdempotencyConflictError):
                    await replay(
                        session,
                        principal_id="dev-principal",
                        method="POST",
                        canonical_path="/api/v1/projects",
                        idempotency_key="key-1",
                        request_hash_value="different-hash",
                    )
        finally:
            await engine.dispose()

    asyncio.run(scenario())
