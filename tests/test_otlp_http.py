from __future__ import annotations

import gzip
import json
from dataclasses import replace

from fastapi.testclient import TestClient
from google.rpc.status_pb2 import Status
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)

import app.main as main_module
from app.main import app


client = TestClient(app)


def reset() -> None:
    response = client.delete("/api/v1/demo/reset")
    assert response.status_code == 200


def _json_request() -> dict:
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "agent-api"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "openai.instrumentation"},
                        "spans": [
                            {
                                "traceId": "00112233445566778899aabbccddeeff",
                                "spanId": "0011223344556677",
                                "name": "chat",
                                "attributes": [
                                    {"key": "gen_ai.provider.name", "value": {"stringValue": "openai"}},
                                    {"key": "gen_ai.request.model", "value": {"stringValue": "gpt-test"}},
                                    {"key": "gen_ai.tool.name", "value": {"stringValue": "refund_customer"}},
                                    {
                                        "key": "loopgrid.test.nested",
                                        "value": {
                                            "kvlistValue": {
                                                "values": [
                                                    {"key": "attempt", "value": {"intValue": "2"}},
                                                    {"key": "ok", "value": {"boolValue": True}},
                                                ]
                                            }
                                        },
                                    },
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }


def _protobuf_request() -> ExportTraceServiceRequest:
    request = ExportTraceServiceRequest()
    resource_spans = request.resource_spans.add()
    resource_attr = resource_spans.resource.attributes.add()
    resource_attr.key = "service.name"
    resource_attr.value.string_value = "agent-api"

    scope_spans = resource_spans.scope_spans.add()
    scope_spans.scope.name = "openai.instrumentation"
    span = scope_spans.spans.add()
    span.trace_id = bytes.fromhex("00112233445566778899aabbccddeeff")
    span.span_id = bytes.fromhex("0011223344556677")
    span.name = "chat"

    provider = span.attributes.add()
    provider.key = "gen_ai.provider.name"
    provider.value.string_value = "openai"

    model = span.attributes.add()
    model.key = "gen_ai.request.model"
    model.value.string_value = "gpt-test"

    tool = span.attributes.add()
    tool.key = "gen_ai.tool.name"
    tool.value.string_value = "refund_customer"

    nested = span.attributes.add()
    nested.key = "loopgrid.test.nested"
    attempt = nested.value.kvlist_value.values.add()
    attempt.key = "attempt"
    attempt.value.int_value = 2
    ok = nested.value.kvlist_value.values.add()
    ok.key = "ok"
    ok.value.bool_value = True
    return request


def _latest_decision() -> dict:
    decisions = client.get("/api/v1/decisions").json()
    assert decisions
    return decisions[0]


def test_otlp_http_json_standard_success_response() -> None:
    reset()
    response = client.post(
        "/v1/traces",
        headers={"Content-Type": "application/json", "X-LoopGrid-Workspace": "default"},
        content=json.dumps(_json_request()).encode("utf-8"),
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["x-loopgrid-accepted"] == "1"
    assert response.json() == {}

    decision = _latest_decision()
    assert decision["model"] == {"provider": "openai", "name": "gpt-test"}
    assert decision["proposed_action"]["tool"] == "refund_customer"
    assert decision["metadata"]["source"] == "otlp-http-json"
    assert decision["metadata"]["otlp_encoding"] == "json"
    assert decision["metadata"]["attributes"]["loopgrid.test.nested"] == {"attempt": 2, "ok": True}


def test_otlp_http_binary_protobuf_success() -> None:
    reset()
    payload = _protobuf_request().SerializeToString()
    response = client.post(
        "/v1/traces",
        headers={"Content-Type": "application/x-protobuf", "X-LoopGrid-Workspace": "default"},
        content=payload,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-protobuf")
    assert response.headers["x-loopgrid-accepted"] == "1"
    parsed = ExportTraceServiceResponse()
    parsed.ParseFromString(response.content)
    assert not parsed.HasField("partial_success")

    decision = _latest_decision()
    assert decision["model"] == {"provider": "openai", "name": "gpt-test"}
    assert decision["context"]["trace_id"] == "00112233445566778899aabbccddeeff"
    assert decision["context"]["span_id"] == "0011223344556677"
    assert decision["metadata"]["source"] == "otlp-http-protobuf"
    assert decision["metadata"]["otlp_encoding"] == "protobuf"
    assert decision["metadata"]["attributes"]["loopgrid.test.nested"] == {"attempt": 2, "ok": True}


def test_otlp_json_and_protobuf_map_equivalently() -> None:
    reset()
    json_response = client.post(
        "/v1/traces",
        headers={"Content-Type": "application/json"},
        content=json.dumps(_json_request()).encode("utf-8"),
    )
    assert json_response.status_code == 200
    json_decision = _latest_decision()

    reset()
    protobuf_response = client.post(
        "/v1/traces",
        headers={"Content-Type": "application/x-protobuf"},
        content=_protobuf_request().SerializeToString(),
    )
    assert protobuf_response.status_code == 200
    protobuf_decision = _latest_decision()

    for key in ("decision_type", "service_name", "agent", "model", "context", "proposed_action"):
        assert json_decision[key] == protobuf_decision[key]
    assert json_decision["metadata"]["attributes"] == protobuf_decision["metadata"]["attributes"]


def test_otlp_http_gzip_protobuf() -> None:
    reset()
    compressed = gzip.compress(_protobuf_request().SerializeToString())
    response = client.post(
        "/v1/traces",
        headers={
            "Content-Type": "application/x-protobuf",
            "Content-Encoding": "gzip",
            "X-LoopGrid-Workspace": "default",
        },
        content=compressed,
    )
    assert response.status_code == 200
    assert response.headers["x-loopgrid-accepted"] == "1"
    assert _latest_decision()["metadata"]["source"] == "otlp-http-protobuf"


def test_otlp_rejects_malformed_protobuf_with_otlp_status() -> None:
    reset()
    response = client.post(
        "/v1/traces",
        headers={"Content-Type": "application/x-protobuf"},
        content=b"\x0a\xff\xff\xff",
    )
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/x-protobuf")
    status = Status()
    status.ParseFromString(response.content)
    assert "Invalid OTLP/HTTP protobuf" in status.message


def test_otlp_rejects_unsupported_content_type() -> None:
    reset()
    response = client.post("/v1/traces", headers={"Content-Type": "text/plain"}, content=b"{}")
    assert response.status_code == 415
    assert response.json()["message"].startswith("Unsupported Content-Type")


def test_otlp_rejects_unsupported_content_encoding() -> None:
    reset()
    response = client.post(
        "/v1/traces",
        headers={"Content-Type": "application/json", "Content-Encoding": "br"},
        content=b"{}",
    )
    assert response.status_code == 415
    assert "Unsupported Content-Encoding" in response.json()["message"]


def test_otlp_limits_decoded_gzip_body(monkeypatch) -> None:
    reset()
    monkeypatch.setattr(main_module, "settings", replace(main_module.settings, max_request_body_bytes=256))
    oversized = json.dumps({"padding": "A" * 2048}).encode("utf-8")
    compressed = gzip.compress(oversized)
    assert len(compressed) < 256
    response = client.post(
        "/v1/traces",
        headers={"Content-Type": "application/json", "Content-Encoding": "gzip"},
        content=compressed,
    )
    assert response.status_code == 413
    assert "Decoded OTLP request body exceeds" in response.json()["message"]


def test_protobuf_ingested_evidence_remains_v1_verifier_compatible(tmp_path) -> None:
    from verifier.loopgrid_verify import verify_bundle

    reset()
    response = client.post(
        "/v1/traces",
        headers={"Content-Type": "application/x-protobuf"},
        content=_protobuf_request().SerializeToString(),
    )
    assert response.status_code == 200
    decision_id = _latest_decision()["decision_id"]
    exported = client.get(f"/api/v1/decisions/{decision_id}/evidence")
    assert exported.status_code == 200
    bundle = tmp_path / "otlp-protobuf-evidence.zip"
    bundle.write_bytes(exported.content)
    verified = verify_bundle(str(bundle))
    assert verified["valid"] is True
    assert verified["bundle_schema"] == "loopgrid/evidence-bundle/2"
    assert verified["signature_algorithm"] == "Ed25519"
