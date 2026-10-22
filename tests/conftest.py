"""Shared fixtures for the end-to-end tool tests.

These tests run each MCP tool against a real Aseprite (ASEPRITE_PATH),
so they are smoke/integration tests, not unit tests. Tests within a
file form a sequence on a module-scoped sprite; files are independent.

Scratch files use a session-scoped pytest directory on the host.
No fixed /tmp path or destructive shared-directory cleanup is needed.
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import aseprite_mcp.tools  # noqa: F401  (registers all tools)
from aseprite_mcp.tools import canvas, drawing



def run(coro):
    """Execute an async tool call from a sync test."""
    return asyncio.run(coro)


def ok(result):
    """Assert a tool call did not return an error message."""
    assert not str(result).startswith(
        ("Failed", "ERROR", "Invalid", "Script failed")
    ), result
    return result


@pytest.fixture(scope="session", autouse=True)
def base_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("aseprite").as_posix()


@pytest.fixture(scope="module")
def sprite(request, base_dir):
    """A fresh 32x32 sprite per test module with a painted 'body' layer."""
    name = request.module.__name__.removeprefix("tests.").removeprefix("test_")
    path = f"{base_dir}/{name}.aseprite"
    ok(run(canvas.create_canvas(32, 32, path)))
    ok(run(canvas.add_layer(path, "body")))
    ok(run(drawing.draw_rectangle_at(path, "body", 1, 8, 8, 16, 16, "#D04648", True)))
    return path
