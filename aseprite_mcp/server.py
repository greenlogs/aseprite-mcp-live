"""MCP exposure profiles, separated from upstream decorator registration."""
import json
import os
from contextlib import asynccontextmanager
from uuid import uuid4

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.fastmcp.utilities.types import Image
from mcp.types import TextContent
from pydantic import ValidationError

from .backends.cli import CliBackend
from .backends.live import LiveBridge
from .core.config import RuntimeConfig
from .core.execution import Executor
from .core.protocol import BackendError, PngPayload


def create_server(profile: str | None = None) -> FastMCP:
    # Importing commands also loads the local .env, without overriding environment.
    profile = profile or os.getenv("ASEPRITE_MCP_TOOL_PROFILE", "core")
    if profile not in {"core", "cli", "all"}:
        raise ValueError("ASEPRITE_MCP_TOOL_PROFILE must be core, cli or all")
    config = RuntimeConfig.from_env()
    executor = Executor(CliBackend(config.limits), config.limits)
    bridge = LiveBridge(executor, config)

    @asynccontextmanager
    async def lifespan(app):
        if profile in {"core", "all"}:
            async with bridge.lifespan():
                yield {"bridge": bridge}
        else:
            yield {}

    server = FastMCP("aseprite", lifespan=lifespan)

    async def dispatch(action, session_id, document_id=None, expected_revision=None,
                       expected_context=None, request_id=None):
        target = {"backend": "live", "session_id": session_id}
        if document_id is not None:
            target["document_id"] = document_id
        result = await executor.execute(json.dumps({"request_id": request_id or str(uuid4()), "target": target,
            "action": action, "expected_revision": expected_revision, "expected_context": expected_context}))
        if not result.ok:
            # FastMCP translates ToolError to an MCP CallToolResult with isError=true.
            raise ToolError(result.model_dump_json())
        return result.model_dump(mode="json")

    if profile in {"core", "all"}:
        @server.tool()
        async def get_connection_status() -> dict:
            """读取实时会话、软件版本及本机连接配置文件位置。"""
            return bridge.status()

        @server.tool()
        async def list_documents(session_id: str) -> dict:
            """列出显式编辑器会话中的内存文档。"""
            return await dispatch({"name": "list_documents"}, session_id)

        @server.tool()
        async def get_document_info(session_id: str, document_id: str) -> dict:
            """读取显式内存文档，标识仅在当前会话有效。"""
            return await dispatch({"name": "get_document_info"}, session_id, document_id)

        @server.tool()
        async def create_sprite(session_id: str, width: int, height: int, request_id: str | None = None) -> dict:
            """创建未保存的 RGB 文档。"""
            return await dispatch({"name": "create_sprite", "width": width, "height": height},
                                  session_id, request_id=request_id)

        @server.tool()
        async def apply_operations(session_id: str, document_id: str, expected_revision: int,
                                   operations: list[dict], expected_context: int | None = None,
                                   request_id: str | None = None) -> dict:
            """在指定修订执行原子批次；操作格式见协议 v1。"""
            return await dispatch({"name": "apply_operations", "operations": operations}, session_id,
                                  document_id, expected_revision, expected_context, request_id)

        @server.tool()
        async def get_preview(session_id: str, document_id: str, expected_revision: int,
                              frame: int = 1, scale: int = 1, region: dict | None = None) -> list:
            """直接返回指定修订/帧的 PNG 图片及元数据；整数最近邻缩放。"""
            result = await dispatch({"name": "get_preview", "frame": frame, "scale": scale, "region": region},
                                    session_id, document_id, expected_revision)
            try:
                png = PngPayload.model_validate(result["data"]["png"])
                raw = png.decode(config.limits)
            except BackendError as exc:
                raise ToolError(f"{exc.code}: {exc.message}") from exc
            except (ValidationError, KeyError, TypeError) as exc:
                raise ToolError("INVALID_REQUEST: Invalid editor PNG payload") from exc
            # Keep metadata once, without duplicating base64 in text content.
            metadata = png.model_dump(mode="json", exclude={"data"})
            result["data"] = {"png": metadata}
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False)),
                    Image(data=raw, format="png")]

        @server.tool()
        async def save_sprite(session_id: str, document_id: str, expected_revision: int,
                              path: str | None = None, overwrite: bool = False,
                              request_id: str | None = None) -> dict:
            """显式保存文档；未命名文档必须指定路径。"""
            return await dispatch({"name": "save_sprite", "path": path, "overwrite": overwrite},
                                  session_id, document_id, expected_revision, request_id=request_id)

        @server.tool()
        async def undo(session_id: str, document_id: str, expected_revision: int,
                       request_id: str | None = None) -> dict:
            """撤销显式文档，要求匹配修订。"""
            return await dispatch({"name": "undo"}, session_id, document_id, expected_revision, request_id=request_id)

        @server.tool()
        async def redo(session_id: str, document_id: str, expected_revision: int,
                       request_id: str | None = None) -> dict:
            """重做显式文档，要求匹配修订。"""
            return await dispatch({"name": "redo"}, session_id, document_id, expected_revision, request_id=request_id)

    if profile in {"cli", "all"}:
        from . import mcp as upstream_registry
        from . import tools  # noqa: F401
        # Pinned MCP 1.6.0 lacks a public registry export. Keep this compatibility
        # seam in one place and verify schemas/calls during upgrades.
        for tool in upstream_registry._tool_manager.list_tools():
            if tool.name != "run_lua_script" or os.getenv("ASEPRITE_MCP_ENABLE_RAW_LUA") == "1":
                server.add_tool(tool.fn, name=tool.name, description=tool.description)

        @server.tool()
        async def cli_execute(request: dict) -> dict:
            """协议 v1 磁盘读取/批量绘制；目标必须明确为 cli。"""
            target = request.get("target")
            if not isinstance(target, dict) or target.get("backend") != "cli":
                raise ToolError("INVALID_TARGET: cli_execute requires a CLI target")
            result = await executor.execute(json.dumps(request))
            if not result.ok:
                raise ToolError(result.model_dump_json())
            return result.model_dump(mode="json")

    return server
