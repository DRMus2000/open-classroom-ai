"""Compatibility Filter for Open WebUI 0.11.2.

It performs no approval, quota, or model call.  The adapter exists only to
preserve a safe attachment reference hook while the Classroom Pipe owns the
single execution path.  Returning a body here can never authorize a request.
"""

from __future__ import annotations


class Filter:
    class Valves:
        enabled: bool = True

    def __init__(self):
        self.valves = self.Valves()

    async def inlet(self, body: dict, __user__: dict | None = None, __metadata__: dict | None = None, **kwargs):
        if not isinstance(body, dict):
            raise ValueError("model body must be an object")
        # The filter is deliberately not a gate and never forwards to an
        # upstream.  RouteGuard/Pipe must have handled authorization first.
        return body

    async def outlet(self, body: dict, **kwargs):
        return body
