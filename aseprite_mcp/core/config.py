"""Direct loopback endpoint configuration; no discovery files or credentials."""
import os
from dataclasses import dataclass, field

from .protocol import Limits

DEFAULT_PORT = 8765


@dataclass(frozen=True)
class RuntimeConfig:
    host: str = "127.0.0.1"
    port: int = DEFAULT_PORT
    limits: Limits = field(default_factory=Limits)

    def __post_init__(self):
        if self.host not in {"127.0.0.1", "::1"} or not 1 <= self.port <= 65535:
            raise ValueError("Live endpoint must be a loopback address and valid port")

    @classmethod
    def from_env(cls, *, host: str | None = None, port: int | None = None):
        values = {}
        for name, info in Limits.model_fields.items():
            value = os.getenv(f"ASEPRITE_MCP_{name.upper()}")
            if value is not None:
                values[name] = float(value) if isinstance(info.default, float) else int(value)
        selected_host = host if host is not None else os.getenv("ASEPRITE_MCP_HOST", "127.0.0.1")
        if selected_host == "localhost":
            selected_host = "127.0.0.1"
        return cls(host=selected_host,
                   port=port if port is not None else int(os.getenv("ASEPRITE_MCP_PORT", str(DEFAULT_PORT))),
                   limits=Limits(**values))
