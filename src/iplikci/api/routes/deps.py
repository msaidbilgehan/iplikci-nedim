"""Who may call a route: the guard has named the sender (a browser or a client with the API token)."""

from collections.abc import Callable

from fastapi import Request

from ..guard import Principal
from ..problems import Problem


def principal_of(request: Request) -> Principal:
    return Principal(request.state.principal)


def only(*allowed: Principal) -> Callable[[Request], Principal]:
    """A dependency that refuses every sender but the allowed ones."""

    def check(request: Request) -> Principal:
        principal = principal_of(request)
        if principal not in allowed:
            raise Problem(403, "forbidden", "Bu işlem bu oturumla yapılamaz.")
        return principal

    return check
