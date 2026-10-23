"""Loopback WebSocket transport; the editor owns all live document operations."""
from __future__ import annotations

import asyncio
import errno
import json
from contextlib import asynccontextmanager
import logging
import os

from pydantic import ValidationError
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from .takeover import terminate_previous_listener

from ..core.protocol import (
    BackendError, LIVE_CAPABILITIES, ErrorCode, Handshake, Request, Result, SERVICE_VERSION, Welcome, failure,
)

log = logging.getLogger(__name__)


class LiveBackend:
    capabilities = LIVE_CAPABILITIES

    def __init__(self, socket):
        self.socket = socket
        self.pending: dict[str, asyncio.Future] = {}

    async def execute(self, request: Request) -> Result:
        future = asyncio.get_running_loop().create_future()
        self.pending[request.request_id] = future
        try:
            await self.socket.send(request.model_dump_json())
            return await future
        except ConnectionClosed as exc:
            raise BackendError(ErrorCode.RESULT_UNKNOWN, "Editor disconnected; refresh before retrying") from exc
        finally:
            self.pending.pop(request.request_id, None)

    def disconnected(self):
        for future in self.pending.values():
            if not future.done():
                future.set_exception(BackendError(ErrorCode.RESULT_UNKNOWN, "Editor disconnected during request"))


class LiveBridge:
    def __init__(self, executor, config):
        self.executor, self.config = executor, config
        self.server = None
        self.hello: Handshake | None = None
        self.url: str | None = None
        self.mcp_handler = None

    def status(self):
        hello = self.hello
        return {"connected": self.executor.live is not None, "session_id": self.executor.session_id,
                "mcp_mode": "shared" if self.mcp_handler is not None else "stdio", "service_pid": os.getpid(),
                "service_version": SERVICE_VERSION, "extension_version": hello.extension_version if hello else None,
                "connection_mode": "direct", "authentication": "none",
                "protocol_version": 1, "capabilities": sorted(self.executor.live_capabilities),
                "enabled_capability_sets": sorted(self.executor.capability_sets),
                "aseprite_version": hello.aseprite_version if hello else None,
                "api_version": hello.api_version if hello else None,
                "url": self.url}

    @asynccontextmanager
    async def lifespan(self):
        # API 28 ixwebsocket sends its ws:// endpoint as Origin. Browser pages
        # send http(s):// (or null); accept only this native form or no Origin.
        host = f"[{self.config.host}]" if ":" in self.config.host else self.config.host
        native_origin = f"ws://{host}:{self.config.port}"
        async def listen():
            return await serve(self._handle, self.config.host, self.config.port,
                               max_size=self.config.limits.max_message_bytes, compression=None,
                               logger=log, origins=[None, native_origin])

        try:
            try:
                listener = await listen()
            except OSError as exc:
                if not self.config.takeover or not self._port_in_use(exc):
                    raise
                # At most one takeover per startup. A competing new listener is
                # never killed again by this process during a bind retry.
                await asyncio.to_thread(terminate_previous_listener, self.config.host, self.config.port)
                deadline = asyncio.get_running_loop().time() + 2
                while True:
                    try:
                        listener = await listen()
                        break
                    except OSError as retry:
                        if not self._port_in_use(retry) or asyncio.get_running_loop().time() >= deadline:
                            raise
                        await asyncio.sleep(.05)
        except OSError as exc:
            raise OSError(f"Cannot listen on {self.config.host}:{self.config.port}; release the port, "
                          f"use --takeover for a previous aseprite-mcp, or choose another --port "
                          f"and match it in the extension. {exc}") from exc
        async with listener as server:
            self.server = server
            host = f"[{self.config.host}]" if ":" in self.config.host else self.config.host
            self.url = f"ws://{host}:{server.sockets[0].getsockname()[1]}"
            try:
                yield self
            finally:
                self.url, self.server = None, None

    @staticmethod
    def _port_in_use(error):
        return error.errno in {errno.EADDRINUSE, 10048} or getattr(error, "winerror", None) == 10048

    async def _handle(self, socket):
        if socket.request.path == "/mcp":
            if self.mcp_handler is None:
                await socket.close(code=1008, reason="Use --shared to start a shared background service")
            else:
                await self.mcp_handler(socket)
            return
        backend = None
        try:
            raw = await asyncio.wait_for(socket.recv(), self.config.limits.timeout_seconds)
            if not isinstance(raw, str):
                raise BackendError(ErrorCode.INVALID_REQUEST, "Expected a JSON text hello")
            hello = Handshake.model_validate_json(raw)
            backend = LiveBackend(socket)
            self.executor.attach_live(backend, hello)
            self.hello = hello
            await socket.send(Welcome(session_id=hello.session_id,
                                      capabilities=sorted(self.executor.live_capabilities),
                                      limits=self.config.limits).model_dump_json())
            async for raw in socket:
                if not isinstance(raw, str):
                    raise BackendError(ErrorCode.INVALID_REQUEST, "Expected JSON text result")
                if json.loads(raw) == {"type": "ping"}:
                    await socket.send('{"type":"pong"}')
                    continue
                result = Result.model_validate_json(raw)
                if result.protocol_version != 1:
                    raise BackendError(ErrorCode.VERSION_MISMATCH, "Result protocol version must be 1")
                future = backend.pending.get(result.request_id)
                # Late receipts after a timeout are discarded, never resubmitted.
                if future is not None and not future.done():
                    future.set_result(result)
        except (ValidationError, ValueError):
            await self._reject(socket, BackendError(ErrorCode.INVALID_REQUEST, "Invalid bridge message"))
        except BackendError as exc:
            await self._reject(socket, exc)
        except TimeoutError:
            await self._reject(socket, BackendError(ErrorCode.TIMEOUT, "Handshake deadline exceeded"))
        except ConnectionClosed:
            pass
        finally:
            if backend is not None:
                backend.disconnected()
                if self.executor.live is backend:
                    self.executor.detach_live()
                    self.hello = None

    @staticmethod
    async def _reject(socket, exc):
        try:
            await socket.send(failure(None, exc).model_dump_json())
            await socket.close(code=1008, reason=exc.code.value)
        except ConnectionClosed:
            pass
