import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)


def require_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    """Overí Bearer token voči zoznamu API_KEYS (porovnanie v konštantnom čase)."""
    if credentials is None:
        raise _unauthorized("Chýba hlavička Authorization: Bearer <API kľúč>.")

    token = credentials.credentials
    if not any(secrets.compare_digest(token, key) for key in settings.api_keys):
        raise _unauthorized("Neplatný API kľúč.")
    return token


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"message": message, "type": "invalid_request_error"}},
        headers={"WWW-Authenticate": "Bearer"},
    )
