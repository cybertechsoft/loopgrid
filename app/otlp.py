from __future__ import annotations

import base64
import gzip
import json
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from google.protobuf.message import DecodeError
from google.rpc.status_pb2 import Status
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)

OTLP_JSON = "application/json"
OTLP_PROTOBUF = "application/x-protobuf"
SUPPORTED_CONTENT_TYPES = {OTLP_JSON, OTLP_PROTOBUF}
SUPPORTED_CONTENT_ENCODINGS = {"", "identity", "gzip"}


@dataclass(frozen=True)
class NormalizedOTLPSpan:
    trace_id: str
    span_id: str
    name: str | None
    scope_name: str | None
    attributes: dict[str, Any]
    source: str


class OTLPHTTPError(ValueError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def media_type_from_header(value: str | None) -> str:
    return (value or "").split(";", 1)[0].strip().lower()


def _read_gzip_limited(raw: bytes, max_bytes: int) -> bytes:
    """Decompress gzip while bounding the decoded body size."""
    try:
        with gzip.GzipFile(fileobj=BytesIO(raw), mode="rb") as stream:
            decoded = stream.read(max_bytes + 1)
    except (OSError, EOFError) as exc:
        raise OTLPHTTPError(400, "Invalid gzip-compressed OTLP request body") from exc
    if len(decoded) > max_bytes:
        raise OTLPHTTPError(413, f"Decoded OTLP request body exceeds {max_bytes} bytes")
    return decoded


def decode_body(raw: bytes, *, content_encoding: str | None, max_bytes: int) -> bytes:
    encoding = (content_encoding or "").strip().lower()
    if encoding not in SUPPORTED_CONTENT_ENCODINGS:
        raise OTLPHTTPError(415, f"Unsupported Content-Encoding: {encoding or '<empty>'}")
    if len(raw) > max_bytes:
        raise OTLPHTTPError(413, f"OTLP request body exceeds {max_bytes} bytes")
    if encoding == "gzip":
        return _read_gzip_limited(raw, max_bytes)
    return raw


def _json_any_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    if "stringValue" in value:
        return value["stringValue"]
    if "boolValue" in value:
        return value["boolValue"]
    if "intValue" in value:
        raw = value["intValue"]
        try:
            return int(raw)
        except (TypeError, ValueError):
            return raw
    if "doubleValue" in value:
        return value["doubleValue"]
    if "arrayValue" in value:
        return [_json_any_value(item) for item in (value.get("arrayValue") or {}).get("values", [])]
    if "kvlistValue" in value:
        return _json_key_values((value.get("kvlistValue") or {}).get("values", []))
    if "bytesValue" in value:
        # OTLP/JSON follows protobuf JSON mapping for bytes and therefore carries base64 text.
        return value["bytesValue"]
    return value


def _json_key_values(attributes: list[dict[str, Any]] | None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for attr in attributes or []:
        key = attr.get("key")
        if key:
            result[key] = _json_any_value(attr.get("value", {}))
    return result


def _protobuf_any_value(value: Any) -> Any:
    kind = value.WhichOneof("value")
    if kind is None:
        return None
    if kind == "array_value":
        return [_protobuf_any_value(item) for item in value.array_value.values]
    if kind == "kvlist_value":
        return {item.key: _protobuf_any_value(item.value) for item in value.kvlist_value.values}
    if kind == "bytes_value":
        return base64.b64encode(value.bytes_value).decode("ascii")
    return getattr(value, kind)


def _protobuf_key_values(attributes: Any) -> dict[str, Any]:
    return {attr.key: _protobuf_any_value(attr.value) for attr in attributes if attr.key}


def parse_otlp_json(body: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(body.decode("utf-8")) if body else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OTLPHTTPError(400, "Invalid OTLP/HTTP JSON request body") from exc
    if not isinstance(parsed, dict):
        raise OTLPHTTPError(400, "OTLP/HTTP JSON request body must be an object")
    return parsed


def parse_otlp_protobuf(body: bytes) -> ExportTraceServiceRequest:
    message = ExportTraceServiceRequest()
    try:
        message.ParseFromString(body)
    except DecodeError as exc:
        raise OTLPHTTPError(400, "Invalid OTLP/HTTP protobuf request body") from exc
    return message


def normalize_json_request(body: dict[str, Any]) -> list[NormalizedOTLPSpan]:
    spans: list[NormalizedOTLPSpan] = []
    for resource_spans in body.get("resourceSpans", []) or []:
        if not isinstance(resource_spans, dict):
            continue
        resource_attrs = _json_key_values((resource_spans.get("resource") or {}).get("attributes", []))
        # scopeSpans is current OTLP. instrumentationLibrarySpans is accepted for older senders.
        scope_spans = resource_spans.get("scopeSpans") or resource_spans.get("instrumentationLibrarySpans") or []
        for scope_group in scope_spans:
            if not isinstance(scope_group, dict):
                continue
            scope = scope_group.get("scope") or scope_group.get("instrumentationLibrary") or {}
            scope_attrs = _json_key_values(scope.get("attributes", [])) if isinstance(scope, dict) else {}
            scope_name = scope.get("name") if isinstance(scope, dict) else None
            for span in scope_group.get("spans", []) or []:
                if not isinstance(span, dict):
                    continue
                attrs = {**resource_attrs, **scope_attrs, **_json_key_values(span.get("attributes", []))}
                trace_id = str(span.get("traceId") or "unknown")
                span_id = str(span.get("spanId") or "")
                spans.append(
                    NormalizedOTLPSpan(
                        trace_id=trace_id,
                        span_id=span_id,
                        name=span.get("name"),
                        scope_name=scope_name,
                        attributes=attrs,
                        source="otlp-http-json",
                    )
                )
    return spans


def normalize_protobuf_request(message: ExportTraceServiceRequest) -> list[NormalizedOTLPSpan]:
    spans: list[NormalizedOTLPSpan] = []
    for resource_spans in message.resource_spans:
        resource_attrs = _protobuf_key_values(resource_spans.resource.attributes)
        for scope_group in resource_spans.scope_spans:
            scope_attrs = _protobuf_key_values(scope_group.scope.attributes)
            for span in scope_group.spans:
                attrs = {**resource_attrs, **scope_attrs, **_protobuf_key_values(span.attributes)}
                spans.append(
                    NormalizedOTLPSpan(
                        trace_id=span.trace_id.hex() if span.trace_id else "unknown",
                        span_id=span.span_id.hex() if span.span_id else "",
                        name=span.name or None,
                        scope_name=scope_group.scope.name or None,
                        attributes=attrs,
                        source="otlp-http-protobuf",
                    )
                )
    return spans


def decode_trace_request(
    raw: bytes,
    *,
    content_type: str | None,
    content_encoding: str | None,
    max_bytes: int,
) -> tuple[str, list[NormalizedOTLPSpan]]:
    media_type = media_type_from_header(content_type)
    if media_type not in SUPPORTED_CONTENT_TYPES:
        raise OTLPHTTPError(
            415,
            "Unsupported Content-Type for OTLP traces; use application/x-protobuf or application/json",
        )
    body = decode_body(raw, content_encoding=content_encoding, max_bytes=max_bytes)
    if media_type == OTLP_PROTOBUF:
        return media_type, normalize_protobuf_request(parse_otlp_protobuf(body))
    return media_type, normalize_json_request(parse_otlp_json(body))


def success_response_body(media_type: str) -> bytes:
    response = ExportTraceServiceResponse()
    if media_type == OTLP_PROTOBUF:
        return response.SerializeToString()
    # Successful OTLP responses leave partialSuccess unset, so JSON is simply {}.
    return b"{}"


def error_response_body(media_type: str, message: str) -> bytes:
    if media_type == OTLP_PROTOBUF:
        return Status(message=message).SerializeToString()
    return json.dumps({"message": message}, separators=(",", ":")).encode("utf-8")
