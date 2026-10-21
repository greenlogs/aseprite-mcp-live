"""Minimal shared execution path with a receipt and staged disk writes."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile

from ..core.commands import AsepriteCommand
from ..core.protocol import BackendError, CliTarget, ErrorCode, Limits, Request, Result, check_limits


class CliBackend:
    capabilities = frozenset({"get_document_info", "apply_operations"})

    def __init__(self, limits: Limits):
        self.limits = limits

    async def execute(self, request: Request) -> Result:
        # subprocess.run has its own deadline and kills/waits its process on timeout.
        return await asyncio.to_thread(self._execute, request)

    def _execute(self, request: Request) -> Result:
        check_limits(request, self.limits)
        if not isinstance(request.target, CliTarget):
            raise BackendError(ErrorCode.INVALID_TARGET, "CLI requires a disk target")
        if request.action.name not in self.capabilities:
            raise BackendError(ErrorCode.UNSUPPORTED_CAPABILITY, request.action.name)
        source = Path(request.target.path)
        if not source.is_absolute() or not source.is_file():
            raise BackendError(ErrorCode.INVALID_TARGET, "CLI requires an existing absolute file path")
        source = source.resolve()
        mutating = request.action.name == "apply_operations"
        # Stage mutations on the same volume, so os.replace is atomic.
        try:
            original_digest = None
            if mutating:
                with source.open("rb") as stream:
                    original_digest = hashlib.file_digest(stream, "sha256").digest()
            with tempfile.TemporaryDirectory(prefix="aseprite-mcp-", dir=source.parent if mutating else None) as scratch:
                root = Path(scratch)
                payload, receipt, artifact = root / "request.json", root / "result.json", root / "edited.aseprite"
                nonce = secrets.token_hex(24)
                payload.write_text(json.dumps({"nonce": nonce,
                    "action": request.action.model_dump(mode="json"),
                    "artifact": artifact.as_posix()}, ensure_ascii=False), encoding="utf-8")
                args = ["--batch", str(source), "--script-param", f"payload={payload.as_posix()}",
                        "--script-param", f"result={receipt.as_posix()}",
                        "--script", str(Path(__file__).with_suffix(".lua"))]
                ok, output = AsepriteCommand.run_command(args, timeout=self.limits.timeout_seconds)
                if not ok:
                    code = ErrorCode.TIMEOUT if "timed out" in output else ErrorCode.EXECUTION_FAILED
                    raise BackendError(code, output or "Aseprite process failed")
                if not receipt.is_file() or receipt.stat().st_size > self.limits.max_message_bytes:
                    raise BackendError(ErrorCode.EXECUTION_FAILED, "Missing or oversized execution receipt")
                try:
                    response = json.loads(receipt.read_text(encoding="utf-8"))
                    if response.get("nonce") != nonce or type(response.get("ok")) is not bool:
                        raise ValueError("Invalid receipt")
                    if not response["ok"]:
                        error = response["error"]
                        raise BackendError(ErrorCode(error["code"]), str(error["message"]))
                    data = response["data"]
                    if not isinstance(data, dict) or not {"width", "height", "layers", "frames"} <= data.keys():
                        raise ValueError("Missing document data")
                except (ValueError, KeyError, TypeError, AttributeError) as exc:
                    raise BackendError(ErrorCode.EXECUTION_FAILED, "Malformed execution receipt") from exc
                if mutating:
                    if not artifact.is_file() or artifact.stat().st_size < 128:
                        raise BackendError(ErrorCode.EXECUTION_FAILED, "Missing fresh output artifact")
                    with artifact.open("rb") as stream:
                        header = stream.read(128)
                    if header[4:6] != b"\xe0\xa5":
                        raise BackendError(ErrorCode.EXECUTION_FAILED, "Invalid Aseprite output artifact")
                    with source.open("rb") as stream:
                        if hashlib.file_digest(stream, "sha256").digest() != original_digest:
                            raise BackendError(ErrorCode.CONTEXT_CONFLICT, "Disk file changed during execution")
                    os.replace(artifact, source)
                return Result(request_id=request.request_id, ok=True, target=request.target, data=data)
        except OSError as exc:
            raise BackendError(ErrorCode.EXECUTION_FAILED, str(exc)) from exc
