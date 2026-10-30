import argparse
import asyncio
import os
import sys

from .core.config import RuntimeConfig
from .server import create_server


def main(argv=None):
    parser = argparse.ArgumentParser(description="Aseprite MCP with a shared local editor background")
    parser.add_argument("--host", help="Loopback listener (default: 127.0.0.1; overrides ASEPRITE_MCP_HOST)")
    parser.add_argument("--port", type=int, help="Listener port (default: 8765; overrides ASEPRITE_MCP_PORT)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--shared", action="store_true", help="Use shared mode (the default for core/all)")
    mode.add_argument("--serve-shared", action="store_true", help="Run the shared loopback background service")
    args = parser.parse_args(argv)
    try:
        config = RuntimeConfig.from_env(host=args.host, port=args.port)
    except ValueError as exc:
        parser.error(str(exc))
    profile = os.getenv("ASEPRITE_MCP_TOOL_PROFILE", "core")
    if profile not in {"core", "all", "cli"}:
        parser.error("ASEPRITE_MCP_TOOL_PROFILE must be core, cli or all")
    if profile != "cli" or args.shared or args.serve_shared:
        from .shared import run_shared_proxy, run_shared_server
        if profile == "cli":
            parser.error("Shared editor mode requires core/all; cli uses disk tools only")
        try:
            asyncio.run((run_shared_server if args.serve_shared else run_shared_proxy)(config, profile))
        except (OSError, ValueError) as exc:
            print(f"Aseprite MCP shared startup/connection failed: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        return
    create_server(config=config).run(transport="stdio")


if __name__ == "__main__":
    main()
