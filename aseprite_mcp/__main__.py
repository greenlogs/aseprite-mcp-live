import argparse
import asyncio
import os
import sys

from .core.config import RuntimeConfig
from .server import create_server


def main(argv=None):
    parser = argparse.ArgumentParser(description="Aseprite MCP stdio server with automatic local editor connection")
    parser.add_argument("--host", help="Loopback listener (default: 127.0.0.1; overrides ASEPRITE_MCP_HOST)")
    parser.add_argument("--port", type=int, help="Listener port (default: 8765; overrides ASEPRITE_MCP_PORT)")
    parser.add_argument("--takeover", action=argparse.BooleanOptionalAction, default=None,
                        help="Terminate a verified previous aseprite-mcp listener on this endpoint (default: off)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--shared", action="store_true", help="Share one background editor connection across stdio clients")
    mode.add_argument("--serve-shared", action="store_true", help="Run the shared loopback background service")
    args = parser.parse_args(argv)
    try:
        config = RuntimeConfig.from_env(host=args.host, port=args.port, takeover=args.takeover)
    except ValueError as exc:
        parser.error(str(exc))
    if args.shared or args.serve_shared:
        from .shared import run_shared_proxy, run_shared_server
        profile = os.getenv("ASEPRITE_MCP_TOOL_PROFILE", "core")
        if config.takeover or profile not in {"core", "all"}:
            parser.error("Shared mode requires core/all and cannot be combined with --takeover")
        try:
            asyncio.run((run_shared_proxy if args.shared else run_shared_server)(config, profile))
        except (OSError, ValueError) as exc:
            print(f"Aseprite MCP shared startup/connection failed: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        return
    create_server(config=config).run(transport="stdio")


if __name__ == "__main__":
    main()
