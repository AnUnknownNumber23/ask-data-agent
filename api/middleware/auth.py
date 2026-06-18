"""JWT authentication middleware."""
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip auth for health check and WebSocket upgrade
        if request.url.path in ("/api/health",) or request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)
        # TODO: Implement JWT validation
        return await call_next(request)
