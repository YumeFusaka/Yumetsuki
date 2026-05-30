use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone)]
pub struct RequestEnvelope {
    pub protocol_version: u32,
    pub request_id: String,
    pub trace_id: String,
    pub parent_trace_id: Option<String>,
    pub session_id: String,
    pub method: String,
    pub params_json: String,
    pub deadline_ms: u64,
}

#[derive(Debug, Clone)]
pub struct ResponseEnvelope {
    pub raw_json: String,
    pub ok: bool,
    pub request_id: Option<String>,
}

impl RequestEnvelope {
    pub fn new(request_id: &str, method: &str, params_json: &str, deadline_ms: u64) -> Self {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|value| value.as_millis())
            .unwrap_or(0);
        Self {
            protocol_version: 1,
            request_id: request_id.to_string(),
            trace_id: format!("trace_{now}_{request_id}"),
            parent_trace_id: None,
            session_id: "rust-supervisor-test".to_string(),
            method: method.to_string(),
            params_json: params_json.to_string(),
            deadline_ms,
        }
    }

    pub fn to_json(&self) -> String {
        let parent = self
            .parent_trace_id
            .as_ref()
            .map(|value| format!("\"{}\"", escape_json(value)))
            .unwrap_or_else(|| "null".to_string());
        format!(
            "{{\"kind\":\"request\",\"protocol_version\":{},\"request_id\":\"{}\",\"trace_id\":\"{}\",\"parent_trace_id\":{},\"session_id\":\"{}\",\"method\":\"{}\",\"params\":{},\"deadline_ms\":{}}}",
            self.protocol_version,
            escape_json(&self.request_id),
            escape_json(&self.trace_id),
            parent,
            escape_json(&self.session_id),
            escape_json(&self.method),
            self.params_json,
            self.deadline_ms
        )
    }
}

impl ResponseEnvelope {
    pub fn from_json(raw_json: &str) -> Result<Self, String> {
        let compact = compact_json(raw_json);
        if !compact.starts_with('{') || !compact.contains("\"kind\":\"response\"") {
            return Err("response frame must be a JSON response object".to_string());
        }
        let ok = extract_bool(&compact, "ok").ok_or_else(|| "response missing ok".to_string())?;
        Ok(Self {
            raw_json: compact.clone(),
            ok,
            request_id: extract_string(&compact, "request_id"),
        })
    }

    pub fn synthetic_error(code: &str) -> Self {
        Self {
            raw_json: format!(
                "{{\"kind\":\"response\",\"ok\":false,\"request_id\":\"synthetic\",\"result\":null,\"error\":{{\"code\":\"{}\"}}}}",
                escape_json(code)
            ),
            ok: false,
            request_id: Some("synthetic".to_string()),
        }
    }

    pub fn result_string(&self, key: &str) -> Option<String> {
        extract_string(&self.raw_json, key)
    }

    pub fn result_i64(&self, key: &str) -> Option<i64> {
        extract_i64(&self.raw_json, key)
    }

    pub fn error_code(&self) -> Option<String> {
        extract_string(&self.raw_json, "code")
    }
}

pub fn escape_json(value: &str) -> String {
    value
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\r', "\\r")
        .replace('\n', "\\n")
}

fn compact_json(value: &str) -> String {
    value.chars().filter(|ch| !ch.is_whitespace()).collect()
}

fn extract_string(raw: &str, key: &str) -> Option<String> {
    let needle = format!("\"{}\":\"", key);
    let start = raw.find(&needle)? + needle.len();
    let rest = &raw[start..];
    let end = rest.find('"')?;
    Some(rest[..end].replace("\\\"", "\"").replace("\\\\", "\\"))
}

fn extract_i64(raw: &str, key: &str) -> Option<i64> {
    let needle = format!("\"{}\":", key);
    let start = raw.find(&needle)? + needle.len();
    let rest = &raw[start..];
    let end = rest
        .find(|ch: char| !ch.is_ascii_digit() && ch != '-')
        .unwrap_or(rest.len());
    rest[..end].parse().ok()
}

fn extract_bool(raw: &str, key: &str) -> Option<bool> {
    let needle = format!("\"{}\":", key);
    let start = raw.find(&needle)? + needle.len();
    let rest = &raw[start..];
    if rest.starts_with("true") {
        Some(true)
    } else if rest.starts_with("false") {
        Some(false)
    } else {
        None
    }
}
