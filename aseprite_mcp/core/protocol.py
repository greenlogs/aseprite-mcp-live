"""Protocol v1. Shared by the future live bridge and the CLI adapter."""
from __future__ import annotations

import base64
import hmac
import io
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

PROTOCOL_VERSION = 1
SERVICE_VERSION = "0.2.0"
CORE_CAPABILITIES = frozenset({
    "list_documents", "get_document_info", "create_sprite", "apply_operations",
    "get_preview", "save_sprite", "undo", "redo",
})


class ErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    SESSION_MISMATCH = "SESSION_MISMATCH"
    NOT_CONNECTED = "NOT_CONNECTED"
    INVALID_TARGET = "INVALID_TARGET"
    REVISION_CONFLICT = "REVISION_CONFLICT"
    CONTEXT_CONFLICT = "CONTEXT_CONFLICT"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    TIMEOUT = "TIMEOUT"
    RESULT_UNKNOWN = "RESULT_UNKNOWN"
    REQUEST_CONFLICT = "REQUEST_CONFLICT"


class BackendError(Exception):
    def __init__(self, code: ErrorCode, message: str):
        self.code, self.message = code, message
        super().__init__(message)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


Identifier = Annotated[str, Field(min_length=1, max_length=128)]
NonNegative = Annotated[int, Field(ge=0)]
Positive = Annotated[int, Field(ge=1)]
Byte = Annotated[int, Field(ge=0, le=255)]


class Limits(Model):
    max_message_bytes: Positive = 8 * 1024 * 1024
    max_operations: Positive = 256
    max_pixels: Positive = 262144
    max_png_bytes: Positive = 4 * 1024 * 1024
    timeout_seconds: Annotated[float, Field(gt=0)] = 30.0
    max_batch_seconds: Annotated[float, Field(gt=0)] = 0.25
    dedup_entries: Positive = 256
    dedup_ttl_seconds: Annotated[float, Field(gt=0)] = 120.0


class Handshake(Model):
    type: Literal["hello"] = "hello"
    protocol_version: int
    token: str = Field(min_length=1, repr=False)
    session_id: Identifier
    aseprite_version: Identifier
    api_version: Positive
    extension_version: Identifier | None = None
    capabilities: list[Identifier]


class Welcome(Model):
    type: Literal["welcome"] = "welcome"
    protocol_version: int = PROTOCOL_VERSION
    session_id: Identifier
    capabilities: list[Identifier]
    limits: Limits


def negotiate(hello: Handshake, token: str) -> frozenset[str]:
    if hello.protocol_version != PROTOCOL_VERSION:
        raise BackendError(ErrorCode.VERSION_MISMATCH, "Protocol version must be 1")
    if hello.extension_version is not None and hello.extension_version != SERVICE_VERSION:
        raise BackendError(ErrorCode.VERSION_MISMATCH, "Install matching service and extension versions")
    if not hmac.compare_digest(hello.token.encode(), token.encode()):
        raise BackendError(ErrorCode.SESSION_MISMATCH, "Invalid startup token")
    if hello.api_version < 28:
        raise BackendError(ErrorCode.UNSUPPORTED_CAPABILITY, "Aseprite API 28+ required")
    return frozenset(hello.capabilities) & CORE_CAPABILITIES


class LiveTarget(Model):
    backend: Literal["live"]
    session_id: Identifier
    document_id: Identifier | None = None


class CliTarget(Model):
    backend: Literal["cli"]
    path: Annotated[str, Field(min_length=1)]


Target = Annotated[LiveTarget | CliTarget, Field(discriminator="backend")]


class LayerRef(Model):
    kind: Literal["id", "ref"] = "id"
    value: Identifier


class CreateLayer(Model):
    op: Literal["create_layer"]
    ref: Identifier
    name: Annotated[str, Field(min_length=1, max_length=256)]


class SetOpacity(Model):
    op: Literal["set_opacity"]
    layer: LayerRef
    opacity: Byte


class Pixel(Model):
    op: Literal["pixel"]
    layer: LayerRef
    frame: Positive = 1
    x: NonNegative
    y: NonNegative
    rgba: tuple[Byte, Byte, Byte, Byte]


class Rectangle(Pixel):
    op: Literal["rectangle"]
    width: Positive
    height: Positive
    filled: bool = True


Edit = Annotated[CreateLayer | SetOpacity | Pixel | Rectangle, Field(discriminator="op")]


class GetInfo(Model):
    name: Literal["get_document_info"]


class ListDocuments(Model):
    name: Literal["list_documents"]


class CreateSprite(Model):
    name: Literal["create_sprite"]
    width: Positive
    height: Positive


class ApplyOperations(Model):
    name: Literal["apply_operations"]
    operations: Annotated[list[Edit], Field(min_length=1)]

    @model_validator(mode="after")
    def check_references(self):
        refs = set()
        for op in self.operations:
            if isinstance(op, CreateLayer):
                if op.ref in refs:
                    raise ValueError("Duplicate batch reference")
                refs.add(op.ref)
            elif op.layer.kind == "ref" and op.layer.value not in refs:
                raise ValueError("Batch references must refer to an earlier create_layer")
        return self


class Region(Model):
    x: NonNegative
    y: NonNegative
    width: Positive
    height: Positive


class GetPreview(Model):
    name: Literal["get_preview"]
    frame: Positive = 1
    scale: Annotated[int, Field(ge=1, le=64)] = 1
    region: Region | None = None


class SaveSprite(Model):
    name: Literal["save_sprite"]
    path: Annotated[str, Field(min_length=1)] | None = None
    overwrite: bool = False


class History(Model):
    name: Literal["undo", "redo"]


Action = Annotated[
    GetInfo | ListDocuments | CreateSprite | ApplyOperations | GetPreview | SaveSprite | History,
    Field(discriminator="name"),
]


class Request(Model):
    protocol_version: int = PROTOCOL_VERSION
    request_id: Identifier
    target: Target
    action: Action
    expected_revision: NonNegative | None = None
    expected_context: NonNegative | None = None
    expected_file_revision: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None

    @model_validator(mode="after")
    def check_target(self):
        if isinstance(self.target, LiveTarget):
            if self.expected_file_revision is not None:
                raise ValueError("File revisions apply only to CLI targets")
            document_action = self.action.name not in {"list_documents", "create_sprite"}
            if document_action != (self.target.document_id is not None):
                raise ValueError("Explicit document target required only for document operations")
            if self.action.name in {"apply_operations", "get_preview", "save_sprite", "undo", "redo"}:
                if self.expected_revision is None:
                    raise ValueError("Expected revision required")
        elif self.expected_revision is not None or self.expected_context is not None:
            raise ValueError("CLI does not provide live revisions or context")
        return self


class Error(Model):
    code: ErrorCode
    message: str


class Result(Model):
    protocol_version: int = PROTOCOL_VERSION
    request_id: Identifier | None
    ok: bool
    target: Target | None = None
    revision: NonNegative | None = None
    context_revision: NonNegative | None = None
    data: dict | None = None
    error: Error | None = None

    @model_validator(mode="after")
    def consistent(self):
        if self.ok == (self.error is not None):
            raise ValueError("Success cannot carry an error; failure must carry one")
        if not self.ok and self.data is not None:
            raise ValueError("Failure cannot carry success data")
        return self


class PngPayload(Model):
    mime_type: Literal["image/png"] = "image/png"
    encoding: Literal["base64"] = "base64"
    data: str
    width: Positive
    height: Positive
    frame: Positive
    scale: Positive
    region: Region | None = None

    def decode(self, limits: Limits) -> bytes:
        if len(self.data) > ((limits.max_png_bytes + 2) // 3) * 4:
            raise BackendError(ErrorCode.LIMIT_EXCEEDED, "PNG payload too large")
        try:
            raw = base64.b64decode(self.data, validate=True)
        except ValueError as exc:
            raise BackendError(ErrorCode.INVALID_REQUEST, "Invalid base64 PNG") from exc
        if len(raw) > limits.max_png_bytes:
            raise BackendError(ErrorCode.LIMIT_EXCEEDED, "PNG payload too large")
        if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
            raise BackendError(ErrorCode.INVALID_REQUEST, "Invalid PNG signature")
        if self.width * self.height > limits.max_pixels:
            raise BackendError(ErrorCode.LIMIT_EXCEEDED, "Preview exceeds pixel budget")
        from PIL import Image
        try:
            with Image.open(io.BytesIO(raw)) as image:
                if image.size != (self.width, self.height) or image.format != "PNG":
                    raise ValueError("PNG dimensions do not match metadata")
                image.verify()
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise BackendError(ErrorCode.INVALID_REQUEST, "Invalid PNG content") from exc
        return raw


def check_limits(request: Request, limits: Limits) -> None:
    if request.protocol_version != PROTOCOL_VERSION:
        raise BackendError(ErrorCode.VERSION_MISMATCH, "Protocol version must be 1")
    action = request.action
    if isinstance(action, CreateSprite) and action.width * action.height > limits.max_pixels:
        raise BackendError(ErrorCode.LIMIT_EXCEEDED, "Canvas exceeds pixel budget")
    if isinstance(action, GetPreview) and action.region is not None:
        if action.region.width * action.region.height * action.scale**2 > limits.max_pixels:
            raise BackendError(ErrorCode.LIMIT_EXCEEDED, "Scaled preview exceeds pixel budget")
    if isinstance(action, ApplyOperations):
        if len(action.operations) > limits.max_operations:
            raise BackendError(ErrorCode.LIMIT_EXCEEDED, "Too many operations")
        pixels = sum(op.width * op.height if isinstance(op, Rectangle) else
                     1 if isinstance(op, Pixel) else 0 for op in action.operations)
        if pixels > limits.max_pixels:
            raise BackendError(ErrorCode.LIMIT_EXCEEDED, "Batch exceeds pixel budget")


def parse_request(raw: str | bytes, limits: Limits) -> Request:
    if len(raw.encode("utf-8") if isinstance(raw, str) else raw) > limits.max_message_bytes:
        raise BackendError(ErrorCode.LIMIT_EXCEEDED, "Message too large")
    try:
        request = Request.model_validate_json(raw)
    except ValidationError as exc:
        raise BackendError(ErrorCode.INVALID_REQUEST, "Invalid request schema") from exc
    check_limits(request, limits)
    return request


def failure(request: Request | None, exc: BackendError) -> Result:
    return Result(request_id=request.request_id if request else None, ok=False,
                  target=request.target if request else None,
                  error=Error(code=exc.code, message=exc.message))
