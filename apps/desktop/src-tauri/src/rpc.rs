use std::sync::atomic::{AtomicU64, Ordering};

use serde::{Deserialize, Serialize};

static REQUEST_COUNTER: AtomicU64 = AtomicU64::new(1);
static TRACE_COUNTER: AtomicU64 = AtomicU64::new(1);

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RpcContext {
    pub request_id: String,
    pub trace_id: String,
    pub parent_trace_id: Option<String>,
    pub session_id: Option<String>,
    pub protocol_version: u16,
    pub deadline_ms: u64,
}

impl RpcContext {
    pub fn new(request_id: String, trace_id: String, session_id: Option<String>) -> Self {
        Self {
            request_id,
            trace_id,
            parent_trace_id: None,
            session_id,
            protocol_version: 1,
            deadline_ms: 30_000,
        }
    }

    pub fn from_inputs(
        request_id: Option<String>,
        trace_id: Option<String>,
        session_id: Option<String>,
        deadline_ms: Option<u64>,
    ) -> Self {
        let request_id =
            request_id.unwrap_or_else(|| format!("req_rust_{}", REQUEST_COUNTER.fetch_add(1, Ordering::Relaxed)));
        let trace_id =
            trace_id.unwrap_or_else(|| format!("trace_rust_{}", TRACE_COUNTER.fetch_add(1, Ordering::Relaxed)));
        let mut context = Self::new(request_id, trace_id, session_id);
        if let Some(deadline_ms) = deadline_ms {
            context.deadline_ms = deadline_ms;
        }
        context
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct RequestEnvelope<T> {
    pub kind: String,
    pub request_id: String,
    pub method: String,
    pub params: T,
    pub protocol_version: u16,
    pub trace_id: String,
    pub parent_trace_id: Option<String>,
    pub session_id: Option<String>,
    pub deadline_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ResponseEnvelope<T> {
    pub kind: String,
    pub request_id: String,
    pub ok: bool,
    pub result: Option<T>,
    pub error: Option<RpcError>,
    pub protocol_version: u16,
    pub trace_id: String,
    pub parent_trace_id: Option<String>,
    pub session_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct EventEnvelope<T> {
    pub kind: String,
    #[serde(rename = "type")]
    pub event_type: String,
    pub request_id: String,
    pub protocol_version: u16,
    pub trace_id: String,
    pub parent_trace_id: Option<String>,
    pub session_id: Option<String>,
    pub sequence: u64,
    pub timestamp_ms: u64,
    pub payload: T,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CommandResponse<T> {
    pub request_id: String,
    pub trace_id: String,
    pub accepted: bool,
    pub result: T,
}

impl<T> CommandResponse<T> {
    pub fn done(context: &RpcContext, result: T) -> Self {
        Self {
            request_id: context.request_id.clone(),
            trace_id: context.trace_id.clone(),
            accepted: false,
            result,
        }
    }

    pub fn accepted(context: &RpcContext, result: T) -> Self {
        Self {
            request_id: context.request_id.clone(),
            trace_id: context.trace_id.clone(),
            accepted: true,
            result,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, thiserror::Error)]
#[error("{code}: {message}")]
pub struct RpcError {
    pub code: String,
    pub message: String,
    pub user_message: String,
    pub retryable: bool,
    pub details: serde_json::Value,
}

impl RpcError {
    pub fn new(
        code: impl Into<String>,
        message: impl Into<String>,
        user_message: impl Into<String>,
        retryable: bool,
        details: serde_json::Value,
    ) -> Self {
        Self {
            code: code.into(),
            message: message.into(),
            user_message: user_message.into(),
            retryable,
            details,
        }
    }

    pub fn sidecar_not_ready() -> Self {
        Self::new(
            "sidecar.not_ready",
            "sidecar 尚未就绪",
            "Sidecar 尚未就绪，请在启动完成后重试。",
            true,
            serde_json::json!({}),
        )
    }

    pub fn sidecar_restarted() -> Self {
        Self::new(
            "sidecar.restarted",
            "sidecar 已重启",
            "Python 内核已重启，请重新发起请求。",
            true,
            serde_json::json!({}),
        )
    }

    pub fn sidecar_busy() -> Self {
        Self::new(
            "sidecar.busy",
            "sidecar 正在处理其他请求",
            "Python 内核正在处理其他请求，请稍后重试。",
            true,
            serde_json::json!({}),
        )
    }

    pub fn request_timeout(request_id: &str, deadline_ms: u64) -> Self {
        Self::new(
            "rpc.request_timeout",
            "RPC 请求超时",
            "请求超时，请稍后重试。",
            true,
            serde_json::json!({ "request_id": request_id, "deadline_ms": deadline_ms }),
        )
    }

    pub fn task_not_found(target_request_id: &str) -> Self {
        Self::new(
            "sidecar.task_not_found",
            "未找到任务",
            "该任务已经不在运行中。",
            false,
            serde_json::json!({ "target_request_id": target_request_id }),
        )
    }

    pub fn invalid_params(field: &str) -> Self {
        Self::new(
            "rpc.invalid_params",
            format!("请求参数缺失或无效: {field}"),
            "请求参数不完整或类型错误。",
            false,
            serde_json::json!({ "field": field }),
        )
    }

    pub fn path_out_of_scope(path: &str) -> Self {
        Self::new(
            "filesystem.path_out_of_scope",
            "路径不在允许范围内",
            "所选路径不在允许的应用数据范围内。",
            false,
            serde_json::json!({ "path": path }),
        )
    }
}

pub fn validate_no_legacy_id(value: &serde_json::Value) -> Result<(), RpcError> {
    match value {
        serde_json::Value::Object(map) => {
            if map.contains_key("id") {
                return Err(RpcError::new(
                    "rpc.invalid_params",
                    "不允许使用旧版 id 字段",
                    "请求格式不受支持。",
                    false,
                    serde_json::json!({ "field": "id" }),
                ));
            }
            for item in map.values() {
                validate_no_legacy_id(item)?;
            }
        }
        serde_json::Value::Array(items) => {
            for item in items {
                validate_no_legacy_id(item)?;
            }
        }
        _ => {}
    }
    Ok(())
}
