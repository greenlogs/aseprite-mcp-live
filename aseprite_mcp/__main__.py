import argparse

from .core.config import RuntimeConfig
from .server import create_server


def main(argv=None):
    parser = argparse.ArgumentParser(description="Aseprite MCP stdio server with automatic local editor connection")
    parser.add_argument("--host", help="Loopback listener (default: 127.0.0.1; overrides ASEPRITE_MCP_HOST)")
    parser.add_argument("--port", type=int, help="Listener port (default: 8765; overrides ASEPRITE_MCP_PORT)")
    parser.add_argument("--takeover", action=argparse.BooleanOptionalAction, default=None,
                        help="Terminate a verified previous aseprite-mcp listener on this endpoint (default: off)")
    args = parser.parse_args(argv)
    try:
        config = RuntimeConfig.from_env(host=args.host, port=args.port, takeover=args.takeover)
    except ValueError as exc:
        parser.error(str(exc))
    create_server(config=config).run(transport="stdio")


if __name__ == "__main__":
    main()
