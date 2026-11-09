from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


def api_error(status_code: int, message: str, type_: str = "invalid_request_error",
              param: str | None = None) -> HTTPException:
    """HTTPException s telom vo formáte OpenAI chýb."""
    return HTTPException(
        status_code=status_code,
        detail={"error": {"message": message, "type": type_, "param": param, "code": None}},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Chyby s OpenAI formátom vráti bez obalu {"detail": ...}."""
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        content = exc.detail
    else:
        content = {"error": {"message": str(exc.detail), "type": "invalid_request_error",
                             "param": None, "code": None}}
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)
