"""Loopback listener configuration; credentials are generated per server startup."""
import os
import secrets
from dataclasses import dataclass, field

from .protocol import Limits


@dataclass(frozen=True)
class RuntimeConfig:
    host: str = "127.0.0.1"
    port: int = 0
    token: str = field(default_factory=lambda: secrets.token_urlsafe(32), repr=False)
    limits: Limits = field(default_factory=Limits)

    def __post_init__(self):
        if self.host not in {"127.0.0.1", "::1"} or not 0 <= self.port <= 65535:
            raise ValueError("Live endpoint must be a loopback address and valid port")

    @classmethod
    def from_env(cls):
        values = {}
        for name, info in Limits.model_fields.items():
            value = os.getenv(f"ASEPRITE_MCP_{name.upper()}")
            if value is not None:
                values[name] = float(value) if isinstance(info.default, float) else int(value)
        return cls(host=os.getenv("ASEPRITE_MCP_HOST", "127.0.0.1"),
                   port=int(os.getenv("ASEPRITE_MCP_PORT", "0")), limits=Limits(**values))
