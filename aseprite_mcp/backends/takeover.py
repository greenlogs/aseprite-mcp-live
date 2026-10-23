"""Opt-in replacement of an identifiable, same-user live listener."""
from __future__ import annotations

import logging
import os
from pathlib import Path
import re

import psutil

log = logging.getLogger(__name__)


def _is_service(process: psutil.Process) -> bool:
    """Recognize supported entrypoints, never a generic Python process."""
    executable = Path(process.exe()).name.lower()
    arguments = process.cmdline()
    if not arguments:
        return False
    if executable in {"aseprite-mcp", "aseprite-mcp.exe"}:
        return True
    if not re.fullmatch(r"python(?:\d+(?:\.\d+)*)?w?(?:\.exe)?", executable):
        return False
    arguments = arguments[1:]
    while arguments and arguments[0] in {"-u", "-B", "-I", "-E", "-s", "-S", "-O", "-OO"}:
        arguments = arguments[1:]
    return (len(arguments) >= 2 and arguments[:2] == ["-m", "aseprite_mcp"] or
            bool(arguments) and Path(arguments[0]).name.lower() in
            {"aseprite-mcp", "aseprite-mcp.exe", "aseprite-mcp-script.py"})


def _listener_pids(host: str, port: int) -> set[int | None]:
    return {connection.pid for connection in psutil.net_connections(kind="tcp")
            if connection.status == psutil.CONN_LISTEN and connection.laddr
            and connection.laddr.ip == host and connection.laddr.port == port}


def terminate_previous_listener(host: str, port: int) -> None:
    """Terminate only the verified listener, with a bounded wait and no tree kill.

    Process identity and ownership are local safeguards, not authentication.
    psutil also checks PID reuse before signalling the Process instance.
    """
    try:
        owners = _listener_pids(host, port)
        if not owners:
            return  # The previous listener may already have exited.
        if len(owners) != 1 or None in owners or os.getpid() in owners:
            raise OSError("Takeover refused: listener owner is unknown or ambiguous")
        process = psutil.Process(next(iter(owners)))
        if process.username() != psutil.Process().username() or not _is_service(process):
            raise OSError("Takeover refused: port belongs to another user or an unrecognized program")
        if "--serve-shared" in process.cmdline():
            raise OSError("Takeover refused: shared background is in use; connect with --shared")
        # Recheck the endpoint after inspecting the command line; never chase a
        # replacement process if ownership changed while we were checking it.
        current = _listener_pids(host, port)
        if not current:
            return
        if current != owners:
            raise OSError("Takeover refused: listener changed during verification")
        log.warning("Taking over %s:%s from previous aseprite-mcp PID %s; old clients disconnect",
                    host, port, process.pid)
        process.terminate()
        process.wait(timeout=5)
    except psutil.NoSuchProcess:
        return
    except (psutil.AccessDenied, psutil.TimeoutExpired) as exc:
        raise OSError("Takeover failed: cannot inspect or stop the previous listener; release the port manually") from exc
