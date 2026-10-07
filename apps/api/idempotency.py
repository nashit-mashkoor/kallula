import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.models import IdempotencyRecord

IDEMPOTENCY_TTL = timedelta(hours=24)


class IdempotencyConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredResponse:
    status: int
    resource_ref: str | None
    snapshot: dict | None


def request_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


async def replay(
    session: AsyncSession,
    *,
    principal_id: str,
    method: str,
    canonical_path: str,
    idempotency_key: str,
    request_hash_value: str,
) -> StoredResponse | None:
    record = (
        await session.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.principal_id == principal_id,
                IdempotencyRecord.method == method,
                IdempotencyRecord.canonical_path == canonical_path,
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
        )
    ).scalar_one_or_none()
    if record is None:
        return None
    if record.request_hash != request_hash_value:
        raise IdempotencyConflictError(idempotency_key)
    return StoredResponse(
        status=record.response_status,
        resource_ref=record.response_resource_ref,
        snapshot=record.response_snapshot_json,
    )


async def store(
    session: AsyncSession,
    *,
    principal_id: str,
    method: str,
    canonical_path: str,
    idempotency_key: str,
    request_hash_value: str,
    status: int,
    resource_ref: str | None = None,
    snapshot: dict | None = None,
) -> None:
    session.add(
        IdempotencyRecord(
            principal_id=principal_id,
            method=method,
            canonical_path=canonical_path,
            idempotency_key=idempotency_key,
            request_hash=request_hash_value,
            response_status=status,
            response_resource_ref=resource_ref,
            response_snapshot_json=snapshot,
            expires_at=datetime.now(UTC) + IDEMPOTENCY_TTL,
        )
    )
