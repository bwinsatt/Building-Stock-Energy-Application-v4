"""Parse Azure Easy Auth identity headers into request state."""

import base64
import json
import logging
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)


@dataclass
class EasyAuthUser:
    principal_name: str | None
    principal_id: str | None
    claims: dict


def parse_client_principal(header_value: str) -> dict:
    try:
        decoded = base64.b64decode(header_value)
        return json.loads(decoded)
    except Exception:
        logger.warning("Failed to decode X-MS-CLIENT-PRINCIPAL header")
        return {}


class EasyAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        principal_name = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
        principal_id = request.headers.get("X-MS-CLIENT-PRINCIPAL-ID")

        claims = {}
        raw_principal = request.headers.get("X-MS-CLIENT-PRINCIPAL")
        if raw_principal:
            claims = parse_client_principal(raw_principal)

        if principal_name or principal_id:
            request.state.user = EasyAuthUser(
                principal_name=principal_name,
                principal_id=principal_id,
                claims=claims,
            )
        else:
            request.state.user = None

        return await call_next(request)
