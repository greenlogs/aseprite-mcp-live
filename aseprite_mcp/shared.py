"""Independent stdio proxies sharing one loopback editor/MCP background."""
from __future__ import annotations

import asyncio
from concurrent.futures import CancelledError
from contextlib import asynccontextmanager
import hashlib
import json
import logging
import os
import socket as network
import subprocess
import sys
import threading
import time

import anyio
from mcp.types import JSONRPCMessage
from pydantic import ValidationError
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, WebSocketException

from .backends.cli import CliBackend
from .backends.live import LiveBridge
from .core.config import RuntimeConfig
from .core.execution import Executor
from .core.protocol import SERVICE_VERSION
from .server import create_server

log = logging.getLogger(__name__)
SHARED_PROTOCOL = "aseprite-mcp-shared-v1"


def configuration_id(config: RuntimeConfig, profile: str) -> str:
    settings = {"version": SERVICE_VERSION, "profile": profile,
                "capability_sets": sorted(config.capability_sets), "limits": config.limits.model_dump(),
                "aseprite_path": os.getenv("ASEPRITE_PATH", "aseprite"),
                "raw_lua": os.getenv("ASEPRITE_MCP_ENABLE_RAW_LUA", "0")}
    return hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()


async def serve_mcp(socket, server):
    """Use a separate SDK ServerSession and JSON-RPC streams per connection."""
    incoming_writer, incoming = anyio.create_memory_object_stream(0)
    outgoing, outgoing_reader = anyio.create_memory_object_stream(0)

    async def receive():
        async with incoming_writer:
            async for raw in socket:
                try:
                    message = JSONRPCMessage.model_validate_json(raw)
                except ValidationError as exc:
                    message = exc
                await incoming_writer.send(message)

    async def send():
        async with outgoing_reader:
            async for message in outgoing_reader:
                await socket.send(message.model_dump_json(by_alias=True, exclude_none=True))

    async with incoming, outgoing:
        tasks = [asyncio.create_task(receive()), asyncio.create_task(send()),
                 asyncio.create_task(server._mcp_server.run(
                     incoming, outgoing, server._mcp_server.create_initialization_options()))]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except ConnectionClosed:
            pass
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


async def run_shared_server(config: RuntimeConfig, profile: str, *, idle_timeout: float = 300):
    if config.takeover or profile not in {"core", "all"}:
        raise ValueError("Shared mode requires core/all and cannot be combined with --takeover")
    bridge = LiveBridge(Executor(CliBackend(config.limits), config.limits,
                                 capability_sets=config.capability_sets), config)
    server = create_server(profile, config=config, bridge=bridge)
    identity = configuration_id(config, profile)
    clients = 0
    last_disconnect = time.monotonic()

    async def handle(socket):
        nonlocal clients, last_disconnect
        clients += 1
        try:
            async with asyncio.timeout(3):
                hello = json.loads(await socket.recv())
            if hello != {"protocol": SHARED_PROTOCOL, "configuration": identity}:
                await socket.send(json.dumps({"protocol": SHARED_PROTOCOL, "error": "Shared configuration mismatch; use matching tool profile, capabilities, limits and Aseprite path"}))
                return
            await socket.send(json.dumps({"protocol": SHARED_PROTOCOL, "pid": os.getpid()}))
            await serve_mcp(socket, server)
        except (ConnectionClosed, TimeoutError, ValueError):
            pass
        finally:
            clients -= 1
            last_disconnect = time.monotonic()

    bridge.mcp_handler = handle
    async with bridge.lifespan():
        while True:
            await asyncio.sleep(min(1, idle_timeout))
            if not clients and not bridge.executor._inflight and time.monotonic() - last_disconnect >= idle_timeout:
                return


def start_background(config: RuntimeConfig, profile: str) -> subprocess.Popen:
    """Detached stdio ensures closing a proxy cannot close the background."""
    env = dict(os.environ, ASEPRITE_MCP_TOOL_PROFILE=profile, ASEPRITE_MCP_TAKEOVER="0",
               ASEPRITE_MCP_CAPABILITY_SETS=",".join(sorted(config.capability_sets)))
    for name, value in config.limits.model_dump().items():
        env[f"ASEPRITE_MCP_{name.upper()}"] = str(value)
    options = {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    return subprocess.Popen([sys.executable, "-m", "aseprite_mcp", "--serve-shared", "--host", config.host,
                             "--port", str(config.port), "--no-takeover"], env=env,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            close_fds=True, **options)


@asynccontextmanager
async def shared_connection(config: RuntimeConfig, profile: str):
    """Only startup is retried; an established connection is never replayed."""
    if config.takeover or profile not in {"core", "all"}:
        raise ValueError("Shared mode requires core/all and cannot be combined with --takeover")
    host = f"[{config.host}]" if ":" in config.host else config.host
    url = f"ws://{host}:{config.port}/mcp"
    deadline = asyncio.get_running_loop().time() + 10
    child = None
    socket = None
    try:
        while socket is None:
            tcp = network.socket(network.AF_INET6 if ":" in config.host else network.AF_INET, network.SOCK_STREAM)
            tcp.setblocking(False)
            try:
                async with asyncio.timeout(1):
                    await asyncio.get_running_loop().sock_connect(tcp, (config.host, config.port))
            except (ConnectionRefusedError, TimeoutError) as exc:
                tcp.close()
                # Start once per proxy. Concurrent children race to bind, but
                # losers never kill the winner or change to another endpoint.
                if child is None:
                    child = start_background(config, profile)
                if asyncio.get_running_loop().time() >= deadline:
                    raise OSError(f"Cannot start shared background on {host}:{config.port}; inspect the port owner") from exc
                await asyncio.sleep(.1)
                continue
            except BaseException:
                tcp.close()
                raise
            try:
                # Separate TCP connection from the WebSocket handshake: on
                # Windows a closed loopback port can time out before refusing.
                socket = await connect(url, sock=tcp, open_timeout=2, max_size=config.limits.max_message_bytes,
                                       compression=None, close_timeout=1, ping_interval=1, ping_timeout=2)
            except (OSError, TimeoutError, WebSocketException) as exc:
                tcp.close()
                raise OSError("Configured endpoint is not an available shared Aseprite MCP service; no process was terminated") from exc
        try:
            await socket.send(json.dumps({"protocol": SHARED_PROTOCOL, "configuration": configuration_id(config, profile)}))
            async with asyncio.timeout(3):
                reply = json.loads(await socket.recv())
            if not isinstance(reply, dict) or reply.get("protocol") != SHARED_PROTOCOL:
                raise OSError("Configured endpoint is not a shared Aseprite MCP service")
            if reply.get("error"):
                raise OSError(reply["error"])
            yield socket, reply["pid"]
        except (ConnectionClosed, TimeoutError, ValueError, KeyError) as exc:
            raise OSError("Shared connection ended; reconnect the MCP client and inspect state before retrying writes") from exc
    finally:
        if socket is not None:
            await socket.close()
        # Reap a losing cold-start child. The binding winner stays independent.
        if child is not None and child.poll() is not None:
            child.wait()


async def run_shared_proxy(config: RuntimeConfig, profile: str):
    async with shared_connection(config, profile) as (socket, _pid):
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue(maxsize=1)

        def enqueue(value):
            operation = queue.put(value)
            try:
                future = asyncio.run_coroutine_threadsafe(operation, loop)
            except RuntimeError:
                operation.close()
                raise
            future.result()

        def read_stdin():
            try:
                pending = bytearray()
                # Read the descriptor directly: a blocked BufferedReader thread
                # holds stdin's lock and can prevent Windows interpreter exit.
                while chunk := os.read(sys.stdin.fileno(), 65536):
                    pending.extend(chunk)
                    while (end := pending.find(b"\n")) != -1:
                        enqueue(bytes(pending[:end + 1]))
                        del pending[:end + 1]
                    if len(pending) > config.limits.max_message_bytes:
                        enqueue(ValueError("MCP message exceeds configured limit"))
                        return
                if pending:
                    enqueue(bytes(pending))
                enqueue(b"")
            except (RuntimeError, OSError, CancelledError):
                return

        # A daemon thread avoids blocking shutdown on a closed backend while
        # the MCP client keeps its stdin pipe open.
        threading.Thread(target=read_stdin, daemon=True).start()

        async def send():
            while line := await queue.get():
                if isinstance(line, Exception):
                    raise line
                if len(line) > config.limits.max_message_bytes:
                    raise ValueError("MCP message exceeds configured limit")
                await socket.send(line.decode("utf-8").rstrip("\r\n"))

        async def receive():
            async for message in socket:
                sys.stdout.buffer.write(message.encode("utf-8") + b"\n")
                sys.stdout.buffer.flush()

        tasks = [asyncio.create_task(send()), asyncio.create_task(receive())]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
