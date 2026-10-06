from contextvars import ContextVar, Token

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return request_id_var.get()


def set_request_id(request_id: str) -> Token[str | None]:
    return request_id_var.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    request_id_var.reset(token)
