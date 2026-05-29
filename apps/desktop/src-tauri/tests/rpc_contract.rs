use yumetsuki_desktop::rpc::{
    validate_no_legacy_id, EventEnvelope, RequestEnvelope, ResponseEnvelope, RpcContext,
};

#[test]
fn rpc_envelopes_serialize_request_id_not_legacy_id() {
    let request = RequestEnvelope {
        kind: "request".to_string(),
        request_id: "req_1".to_string(),
        method: "sidecar.hello".to_string(),
        params: serde_json::json!({}),
        protocol_version: 1,
        trace_id: "trace_1".to_string(),
        parent_trace_id: None,
        session_id: None,
        deadline_ms: 30000,
    };
    let encoded = serde_json::to_value(request).expect("序列化 request");
    assert!(encoded.get("request_id").is_some());
    assert!(encoded.get("id").is_none());
    validate_no_legacy_id(&encoded).expect("request 不应包含旧版 id");
}

#[test]
fn validate_no_legacy_id_rejects_nested_id_fields() {
    let payload = serde_json::json!({
        "request_id": "req_1",
        "params": {
            "id": "legacy"
        }
    });
    let err = validate_no_legacy_id(&payload).expect_err("旧版 id 必须被拒绝");
    assert_eq!(err.code, "rpc.invalid_params");
}

#[test]
fn response_and_event_have_canonical_fields() {
    let context = RpcContext::new("req_1".into(), "trace_1".into(), Some("session_1".into()));
    let response = ResponseEnvelope {
        kind: "response".to_string(),
        request_id: context.request_id.clone(),
        ok: true,
        result: Some(serde_json::json!({"status": "ready"})),
        error: None,
        protocol_version: context.protocol_version,
        trace_id: context.trace_id.clone(),
        parent_trace_id: context.parent_trace_id.clone(),
        session_id: context.session_id.clone(),
    };
    let event = EventEnvelope {
        kind: "event".to_string(),
        event_type: "chat.delta".to_string(),
        request_id: context.request_id,
        protocol_version: context.protocol_version,
        trace_id: context.trace_id,
        parent_trace_id: context.parent_trace_id,
        session_id: context.session_id,
        sequence: 1,
        timestamp_ms: 1,
        payload: serde_json::json!({"text": "hello"}),
    };

    assert_eq!(response.kind, "response");
    assert_eq!(response.ok, true);
    assert_eq!(event.kind, "event");
    assert_eq!(event.event_type, "chat.delta");
    assert_eq!(event.sequence, 1);
}
