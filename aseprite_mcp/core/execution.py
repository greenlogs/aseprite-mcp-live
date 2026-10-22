"""Shared routing and bounded session deduplication. No transport in P0."""
from __future__ import annotations

import asyncio
from collections import OrderedDict
import hashlib
import os
import logging
import time
from typing import Protocol

from .protocol import (
    BackendError, ErrorCode, Handshake, Limits, LiveTarget, Request, Result, failure,
    LIVE_WRITES, negotiate, parse_request,
)

log = logging.getLogger(__name__)


class Backend(Protocol):
    capabilities: frozenset[str]

    async def execute(self, request: Request) -> Result: ...


class Executor:
    def __init__(self, cli: Backend, limits: Limits | None = None, *, capability_sets: frozenset[str] = frozenset()):
        self.limits = limits or Limits()
        self.capability_sets = capability_sets
        self.cli = cli
        self.live: Backend | None = None
        self.session_id: str | None = None
        self.live_capabilities: frozenset[str] = frozenset()
        self._cache = OrderedDict()
        self._locks = {}
        self._inflight = {}

    def attach_live(self, backend: Backend, hello: Handshake):
        capabilities = negotiate(hello, self.capability_sets)
        if self.live is not None:
            raise BackendError(ErrorCode.SESSION_MISMATCH, "An editor is already attached")
        self.live, self.session_id = backend, hello.session_id
        self.live_capabilities = capabilities & backend.capabilities
        self._clear_live_cache()

    def detach_live(self):
        self.live, self.session_id = None, None
        self.live_capabilities = frozenset()
        self._clear_live_cache()

    def _clear_live_cache(self):
        # Reconnecting the editor must not remove disk-write receipts.
        for key in list(self._cache):
            if key[0] == "live":
                del self._cache[key]

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
            key = (request.target.backend, request.target.session_id if isinstance(request.target, LiveTarget) else None,
                   request.request_id)
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
            if key in self._inflight:
                old_digest, task = self._inflight[key]
                if digest != old_digest:
                    raise BackendError(ErrorCode.REQUEST_CONFLICT, "Request ID reused while executing")
            else:
                if len(self._inflight) >= self.limits.dedup_entries:
                    raise BackendError(ErrorCode.LIMIT_EXCEEDED, "Request queue full; refresh before retrying")
                task = asyncio.create_task(self._execute(request, backend, key, digest))
                self._inflight[key] = (digest, task)
            # MCP cancellation cancels the waiter, never an accepted write or its receipt.
            return await asyncio.shield(task)
        except BackendError as exc:
            return failure(request, exc)

    async def _execute(self, request, backend, key, digest):
        queued = time.perf_counter()
        started = queued
        resource = ("live", request.target.session_id) if isinstance(request.target, LiveTarget) else (
            "cli", os.path.normcase(os.path.realpath(request.target.path)))
        lock, users = self._locks.get(resource, (asyncio.Lock(), 0))
        self._locks[resource] = (lock, users + 1)
        acquired = False
        try:
            try:
                await asyncio.wait_for(lock.acquire(), self.limits.timeout_seconds)
                acquired = True
                started = time.perf_counter()
            except TimeoutError as exc:
                raise BackendError(ErrorCode.TIMEOUT, "Queue deadline exceeded; request was not sent") from exc
            if acquired:
                if isinstance(request.target, LiveTarget) and (
                    self.live is not backend or request.target.session_id != self.session_id
                ):
                    raise BackendError(ErrorCode.SESSION_MISMATCH, "Session changed while queued")
                try:
                    if isinstance(request.target, LiveTarget):
                        try:
                            result = await asyncio.wait_for(backend.execute(request), self.limits.timeout_seconds)
                        except TimeoutError as exc:
                            code = ErrorCode.RESULT_UNKNOWN if request.action.name in LIVE_WRITES else ErrorCode.TIMEOUT
                            raise BackendError(code, "Live request deadline exceeded") from exc
                    else:
                        result = await backend.execute(request)
                    if result.request_id != request.request_id or result.target != request.target:
                        raise BackendError(ErrorCode.RESULT_UNKNOWN, "Mismatched backend response")
                except BackendError as exc:
                    result = failure(request, exc)
                except Exception:
                    log.exception("Backend failed without a receipt")
                    code = ErrorCode.RESULT_UNKNOWN if isinstance(request.target, LiveTarget) else ErrorCode.EXECUTION_FAILED
                    result = failure(request, BackendError(code, "Backend failed without a receipt"))
        except BackendError as exc:
            result = failure(request, exc)
        finally:
            log.info("execution backend=%s queue_ms=%.2f run_ms=%.2f", request.target.backend,
                     (started - queued) * 1000, (time.perf_counter() - started) * 1000)
            if acquired:
                lock.release()
            _, users = self._locks[resource]
            if users == 1:
                del self._locks[resource]
            else:
                self._locks[resource] = (lock, users - 1)
            self._inflight.pop(key, None)
        # An old connection completing must not populate the new session's cache.
        if not isinstance(request.target, LiveTarget) or self.live is backend:
            self._cache[key] = (time.monotonic(), digest, result)
            while len(self._cache) > self.limits.dedup_entries:
                self._cache.popitem(last=False)
        return result
