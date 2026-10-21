"""Loopback WebSocket transport; the editor owns all live document operations."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
import logging
import os
from pathlib import Path
import tempfile
from uuid import uuid4

from pydantic import ValidationError
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from ..core.protocol import (
    BackendError, CORE_CAPABILITIES, ErrorCode, Handshake, Request, Result, SERVICE_VERSION, Welcome, failure,
)

log = logging.getLogger(__name__)


class LiveBackend:
    capabilities = CORE_CAPABILITIES

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
        self.connection_file = Path(os.getenv("ASEPRITE_MCP_CONNECTION_FILE") or
                                    Path(tempfile.gettempdir()) / f"aseprite-mcp-{os.getpid()}-{uuid4().hex}.json")

    def status(self):
        hello = self.hello
        return {"connected": self.executor.live is not None, "session_id": self.executor.session_id,
                "service_version": SERVICE_VERSION, "extension_version": hello.extension_version if hello else None,
                "protocol_version": 1, "capabilities": sorted(self.executor.live_capabilities),
                "aseprite_version": hello.aseprite_version if hello else None,
                "api_version": hello.api_version if hello else None,
                "url": self.url, "connection_file": str(self.connection_file) if self.url else None}

    @asynccontextmanager
    async def lifespan(self):
        # Bind before advertising. A port collision fails startup, never CLI fallback.
        async with serve(self._handle, self.config.host, self.config.port,
                         max_size=self.config.limits.max_message_bytes, compression=None,
                         logger=log) as server:
            self.server = server
            host = f"[{self.config.host}]" if ":" in self.config.host else self.config.host
            self.url = f"ws://{host}:{server.sockets[0].getsockname()[1]}"
            try:
                # Exclusive creation prevents replacing another process's discovery file.
                try:
                    fd = os.open(self.connection_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                except FileExistsError as exc:
                    raise RuntimeError("Connection file already exists; select a new path or confirm the old server has exited before removing it") from exc
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    json.dump({"url": self.url, "token": self.config.token}, stream)
                log.warning("Live connection file: %s", self.connection_file)
                yield self
            finally:
                if self.connection_file.exists():
                    # Never remove another process's file, including on failed creation.
                    try:
                        if json.loads(self.connection_file.read_text(encoding="utf-8")).get("token") == self.config.token:
                            self.connection_file.unlink()
                    except (OSError, ValueError):
                        log.warning("Could not clean live connection file")
                self.url, self.server = None, None

    async def _handle(self, socket):
        backend = None
        try:
            raw = await asyncio.wait_for(socket.recv(), self.config.limits.timeout_seconds)
            if not isinstance(raw, str):
                raise BackendError(ErrorCode.INVALID_REQUEST, "Expected a JSON text hello")
            hello = Handshake.model_validate_json(raw)
            backend = LiveBackend(socket)
            self.executor.attach_live(backend, hello, self.config.token)
            self.hello = hello
            await socket.send(Welcome(session_id=hello.session_id,
                                      capabilities=sorted(self.executor.live_capabilities),
                                      limits=self.config.limits).model_dump_json())
            async for raw in socket:
                if not isinstance(raw, str):
                    raise BackendError(ErrorCode.INVALID_REQUEST, "Expected JSON text result")
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
