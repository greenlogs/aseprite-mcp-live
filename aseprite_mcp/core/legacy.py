"""Keep upstream async signatures while running their synchronous bodies off-loop."""
import asyncio
from functools import wraps
import inspect

from mcp.server.fastmcp.exceptions import ToolError

from .files import disk_access
from .protocol import BackendError, ErrorCode, failure


def worker_tool(fn):
    signature = inspect.signature(fn)

    @wraps(fn)
    async def call(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        paths = [value for name, value in bound.arguments.items()
                 if (name.endswith("filename") or name.endswith("_path")) and isinstance(value, str)]

        def execute():
            with disk_access(paths):
                return asyncio.run(fn(*args, **kwargs))

        task = asyncio.create_task(asyncio.to_thread(execute))
        try:
            result = await asyncio.shield(task)
        except BackendError as exc:
            raise ToolError(failure(None, exc).model_dump_json()) from exc
        if isinstance(result, str) and result.startswith(("Failed", "ERROR", "Invalid", "Script failed")):
            raise ToolError(failure(None, BackendError(ErrorCode.EXECUTION_FAILED, result)).model_dump_json())
        return result

    return call
