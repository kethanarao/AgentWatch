"""Single-process admission limits. Do not trust client-supplied forwarding headers."""

import asyncio
import math
import time
from collections import deque

from starlette.responses import JSONResponse


class PublicActionGuard:
    def __init__(self, app, config):
        self.app, self.config = app, config
        self.recent = deque()
        self.heavy_recent = deque()
        self.active = 0
        self.heavy_active = 0

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or not scope["path"].startswith("/api/")
        ):
            return await self.app(scope, receive, send)

        async def reject(code, detail, retry=None):
            headers = {"Retry-After": str(retry)} if retry is not None else None
            await JSONResponse({"detail": detail}, status_code=code, headers=headers)(
                scope, receive, send
            )

        c = self.config
        heavy = scope["path"] in {"/api/regression/run", "/api/experiments/run", "/api/drift/demo"}
        now = time.monotonic()
        for history, window in [(self.recent, 60), (self.heavy_recent, 600)]:
            while history and now - history[0] >= window:
                history.popleft()
        if self.active >= c.public_max_active or (heavy and self.heavy_active):
            return await reject(429, "The demo is busy. Please retry shortly.", 5)
        if len(self.recent) >= c.public_requests_per_minute:
            return await reject(
                429,
                "Shared demo request limit reached.",
                max(1, math.ceil(60 - (now - self.recent[0]))),
            )
        if heavy and len(self.heavy_recent) >= c.public_benchmarks_per_10_minutes:
            return await reject(
                429,
                "Shared experiment/regression/drift budget reached.",
                max(1, math.ceil(600 - (now - self.heavy_recent[0]))),
            )
        # Global budgets remain effective behind a proxy and cannot be bypassed by forged IPs.
        self.recent.append(now)
        if heavy:
            self.heavy_recent.append(now)
        self.active += 1
        self.heavy_active += int(heavy)
        started = False

        async def tracked_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            async with asyncio.timeout(c.public_request_timeout_seconds):
                body = bytearray()
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    body.extend(message.get("body", b""))
                    if len(body) > c.public_max_body_bytes:
                        return await reject(413, "Request body exceeds the demo limit.")
                    if not message.get("more_body", False):
                        break
                delivered = False

                async def replay():
                    nonlocal delivered
                    if not delivered:
                        delivered = True
                        return {"type": "http.request", "body": bytes(body), "more_body": False}
                    return await receive()

                await self.app(scope, replay, tracked_send)
        except TimeoutError:
            if not started:
                await reject(504, "Request exceeded its time budget. Try a smaller request.")
        finally:
            self.active -= 1
            self.heavy_active -= int(heavy)
