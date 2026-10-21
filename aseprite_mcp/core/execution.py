"""Shared routing and bounded session deduplication. No transport in P0."""
from __future__ import annotations

import asyncio
from collections import OrderedDict
import hashlib
import time
from typing import Protocol

from .protocol import (
    BackendError, ErrorCode, Handshake, Limits, LiveTarget, Request, Result, failure,
    negotiate, parse_request,
)


class Backend(Protocol):
    capabilities: frozenset[str]

    async def execute(self, request: Request) -> Result: ...


class Executor:
    def __init__(self, cli: Backend, limits: Limits | None = None):
        self.limits = limits or Limits()
        self.cli = cli
        self.live: Backend | None = None
        self.session_id: str | None = None
        self.live_capabilities: frozenset[str] = frozenset()
        self._cache = OrderedDict()
        self._lock = asyncio.Lock()

    def attach_live(self, backend: Backend, hello: Handshake, token: str):
        capabilities = negotiate(hello, token)
        if self.live is not None:
            raise BackendError(ErrorCode.SESSION_MISMATCH, "An editor is already attached")
        self.live, self.session_id = backend, hello.session_id
        self.live_capabilities = capabilities & backend.capabilities
        self._cache.clear()

    def detach_live(self):
        self.live, self.session_id = None, None
        self.live_capabilities = frozenset()
        self._cache.clear()

    async def execute(self, raw: str | bytes) -> Result:
        request = None
        try:
            request = parse_request(raw, self.limits)
            if isinstance(request.target, LiveTarget):
                if self.live is None:
                    raise BackendError(ErrorCode.NOT_CONNECTED, "No editor connected")
                if request.target.session_id != self.session_id:
                    raise BackendError(ErrorCode.SESSION_MISMATCH, "Stale editor session")
                backend = self.live
            else:
                backend = self.cli
            capabilities = self.live_capabilities if isinstance(request.target, LiveTarget) else backend.capabilities
            if request.action.name not in capabilities:
                raise BackendError(ErrorCode.UNSUPPORTED_CAPABILITY, request.action.name)
            # A single serialized queue bounds concurrent mutations and duplicate requests.
            async with self._lock:
                if isinstance(request.target, LiveTarget) and (
                    self.live is not backend or request.target.session_id != self.session_id
                ):
                    raise BackendError(ErrorCode.SESSION_MISMATCH, "Session changed while queued")
                key = (request.target.backend, self.session_id, request.request_id)
                digest = hashlib.sha256(request.model_dump_json().encode()).digest()
                now = time.monotonic()
                for old in list(self._cache):
                    if now - self._cache[old][0] >= self.limits.dedup_ttl_seconds:
                        del self._cache[old]
                if key in self._cache:
                    _, old_digest, result = self._cache[key]
                    if digest != old_digest:
                        raise BackendError(ErrorCode.REQUEST_CONFLICT, "Request ID reused with different payload")
                    return result
                try:
                    if isinstance(request.target, LiveTarget):
                        try:
                            result = await asyncio.wait_for(backend.execute(request), self.limits.timeout_seconds)
                        except TimeoutError as exc:
                            code = ErrorCode.RESULT_UNKNOWN if request.action.name in {
                                "apply_operations", "create_sprite", "save_sprite", "undo", "redo"
                            } else ErrorCode.TIMEOUT
                            raise BackendError(code, "Live request deadline exceeded") from exc
                    else:
                        result = await backend.execute(request)
                    if result.request_id != request.request_id or result.target != request.target:
                        raise BackendError(ErrorCode.RESULT_UNKNOWN, "Mismatched backend response")
                except BackendError as exc:
                    result = failure(request, exc)
                except Exception:
                    code = ErrorCode.RESULT_UNKNOWN if isinstance(request.target, LiveTarget) else ErrorCode.EXECUTION_FAILED
                    result = failure(request, BackendError(code, "Backend failed without a receipt"))
                self._cache[key] = (time.monotonic(), digest, result)
                while len(self._cache) > self.limits.dedup_entries:
                    self._cache.popitem(last=False)
                return result
        except BackendError as exc:
            return failure(request, exc)
