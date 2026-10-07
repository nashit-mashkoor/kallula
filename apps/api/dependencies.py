from collections.abc import AsyncIterator

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.session import resolve_principal


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = request.app.state.session_factory
    async with factory() as session:
        yield session


async def get_principal_id(request: Request) -> str:
    principal = resolve_principal(request.app.state.settings)
    if principal is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return principal.id
