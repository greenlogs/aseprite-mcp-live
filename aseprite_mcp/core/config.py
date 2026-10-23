"""Direct loopback endpoint configuration; no discovery files or credentials."""
import os
from dataclasses import dataclass, field

from .protocol import CAPABILITY_SETS, Limits

DEFAULT_PORT = 8765


@dataclass(frozen=True)
class RuntimeConfig:
    host: str = "127.0.0.1"
    port: int = DEFAULT_PORT
    limits: Limits = field(default_factory=Limits)
    capability_sets: frozenset[str] = frozenset()
    takeover: bool = False

    def __post_init__(self):
        if self.host not in {"127.0.0.1", "::1"} or not 1 <= self.port <= 65535:
            raise ValueError("Live endpoint must be a loopback address and valid port")
        if self.capability_sets - CAPABILITY_SETS.keys():
            raise ValueError("Unknown ASEPRITE_MCP_CAPABILITY_SETS; supported: animation")

    @classmethod
    def from_env(cls, *, host: str | None = None, port: int | None = None,
                 takeover: bool | None = None):
        values = {}
        for name, info in Limits.model_fields.items():
            value = os.getenv(f"ASEPRITE_MCP_{name.upper()}")
            if value is not None:
                values[name] = float(value) if isinstance(info.default, float) else int(value)
        selected_host = host if host is not None else os.getenv("ASEPRITE_MCP_HOST", "127.0.0.1")
        if selected_host == "localhost":
            selected_host = "127.0.0.1"
        selected_takeover = os.getenv("ASEPRITE_MCP_TAKEOVER", "0").strip().lower()
        if takeover is None and selected_takeover not in {"0", "1", "false", "true"}:
            raise ValueError("ASEPRITE_MCP_TAKEOVER must be 0, 1, false or true")
        return cls(host=selected_host,
                   port=port if port is not None else int(os.getenv("ASEPRITE_MCP_PORT", str(DEFAULT_PORT))),
                   takeover=takeover if takeover is not None else selected_takeover in {"1", "true"},
                   limits=Limits(**values), capability_sets=frozenset(
                       name.strip() for name in os.getenv("ASEPRITE_MCP_CAPABILITY_SETS", "").split(",") if name.strip()))
