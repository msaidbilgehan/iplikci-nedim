"""Errors as `application/problem+json` (RFC 9457): a machine code and a Turkish message for the user. What went
wrong inside goes to the log only (ADR-0007)."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

log = logging.getLogger("iplikci.api")

_TITLES = {
    400: "İstek anlaşılamadı.",
    404: "Böyle bir adres yok.",
    405: "Bu adres bu yöntemi kabul etmiyor.",
}


class Problem(Exception):
    """An answer the API gives on purpose: the status, a machine code and the Turkish message."""

    def __init__(self, status: int, code: str, title: str) -> None:
        super().__init__(title)
        self.status = status
        self.code = code
        self.title = title


def problem(status: int, code: str, title: str) -> JSONResponse:
    return JSONResponse(
        {"type": f"urn:iplikci:problem:{code}", "title": title, "status": status, "code": code},
        status_code=status,
        media_type="application/problem+json",
    )


def install(app: FastAPI) -> None:
    async def on_problem(_request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, Problem)
        return problem(exc.status, exc.code, exc.title)

    async def on_invalid(_request: Request, _exc: Exception) -> JSONResponse:
        return problem(422, "invalid_request", "İstekteki değerler geçersiz.")

    async def on_http(_request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, HTTPException)
        title = _TITLES.get(exc.status_code, "İstek yerine getirilemedi.")
        return problem(exc.status_code, f"http_{exc.status_code}", title)

    async def on_crash(request: Request, exc: Exception) -> JSONResponse:
        log.error("request failed: %s %s", request.method, request.url.path, exc_info=exc)
        return problem(500, "internal", "Beklenmeyen bir hata oldu; ayrıntısı günlükte.")

    app.add_exception_handler(Problem, on_problem)
    app.add_exception_handler(RequestValidationError, on_invalid)
    app.add_exception_handler(HTTPException, on_http)
    app.add_exception_handler(Exception, on_crash)
