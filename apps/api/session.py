from fastapi import APIRouter
from pydantic import BaseModel
from starlette.requests import Request

from api.settings import Settings

router = APIRouter(tags=["session"])


class Principal(BaseModel):
    id: str
    display_name: str
    email: str | None = None


class Session(BaseModel):
    authenticated: bool
    principal: Principal | None = None
    session_expires_at: str | None = None


def resolve_principal(settings: Settings) -> Principal | None:
    if not settings.development_mode or settings.auth_mode != "development":
        return None
    return Principal(
        id=settings.dev_principal_id,
        display_name=settings.dev_principal_display_name,
        email=settings.dev_principal_email,
    )


@router.get("/session")
async def get_session(request: Request) -> Session:
    settings: Settings = request.app.state.settings
    principal = resolve_principal(settings)
    if principal is None:
        return Session(authenticated=False)
    return Session(authenticated=True, principal=principal, session_expires_at=None)
