pub mod audio;
pub mod capability_manifest;
pub mod command_catalog;
pub mod path_scope;
pub mod recorder;
pub mod rpc;
pub mod runtime_paths;
pub mod sidecar;

use std::sync::{Arc, Mutex};

use serde::Deserialize;
use serde_json::{json, Value};
use tauri::{Emitter, Manager};

use rpc::{CommandResponse, RpcContext, RpcError};
use runtime_paths::{RuntimeMode, RuntimePaths};
use sidecar::{
    CancelResult, ConfigSnapshot, HealthResult, HelloResult, LogsQueryResult, ShutdownResult,
    SidecarEventBridge, SidecarSupervisor,
};

#[derive(Clone)]
pub struct AppState {
    supervisor: Arc<Mutex<SidecarSupervisor>>,
    runtime_paths: RuntimePaths,
}

#[derive(Debug, Default, Deserialize)]
struct InvocationContext {
    request_id: Option<String>,
    trace_id: Option<String>,
    parent_trace_id: Option<String>,
    session_id: Option<String>,
    deadline_ms: Option<u64>,
}

#[derive(Debug, Default, Deserialize)]
struct EmptyParams {}

#[derive(Debug, Default, Deserialize)]
struct CancelParams {
    request_id: Option<String>,
    reason: Option<String>,
}

#[derive(Debug, Default, Deserialize)]
struct ChatSendParams {
    text: Option<String>,
    message: Option<String>,
    session_id: Option<String>,
    visual_handle: Option<Value>,
}

#[derive(Debug, Default, Deserialize)]
struct ChatRetryParams {
    request_id: Option<String>,
    source_request_id: Option<String>,
    retry_policy: Option<Value>,
}

#[derive(Debug, Default, Deserialize)]
struct ConfigSaveSystemParams {
    snapshot: Option<Value>,
    draft: Option<Value>,
    base_version: Option<u64>,
    confirm_token: Option<String>,
}

#[derive(Debug, Default, Deserialize)]
struct DiagnosticsRunParams {
    checks: Option<Vec<String>>,
    include_sensitive: Option<bool>,
}

#[derive(Debug, Default, Deserialize)]
struct DiagnosticsExportParams {
    report_handle: Option<String>,
    format: Option<String>,
}

#[derive(Debug, Default, Deserialize)]
struct ScopeParams {
    scope: Option<String>,
}

#[derive(Debug, Default, Deserialize)]
struct LimitParams {
    limit: Option<usize>,
}

#[derive(Debug, Default, Deserialize)]
struct IncludeDisabledParams {
    include_disabled: Option<bool>,
}

#[derive(Debug, Default, Deserialize)]
struct ToolsCallParams {
    tool_name: Option<String>,
    source: Option<String>,
    arguments: Option<Value>,
    dry_run: Option<bool>,
    confirm_token: Option<String>,
}

#[derive(Debug, Default, Deserialize)]
struct AuditQueryParams {
    limit: Option<usize>,
    cursor: Option<String>,
    filters: Option<Value>,
}

#[derive(Debug, Default, Deserialize)]
struct FiltersParams {
    filters: Option<Value>,
}

#[derive(Debug, Default, Deserialize)]
struct PluginStatusParams {
    plugin_id: Option<String>,
}

#[derive(Debug, Default, Deserialize)]
struct PluginToggleParams {
    plugin_id: Option<String>,
    confirm_token: Option<String>,
}

#[derive(Debug, Default, Deserialize)]
struct McpRefreshParams {
    server_id: Option<String>,
}

#[derive(Debug, Default, Deserialize)]
struct McpCallToolParams {
    server_id: Option<String>,
    tool_name: Option<String>,
    arguments: Option<Value>,
    confirm_token: Option<String>,
}

impl AppState {
    pub fn new(runtime_paths: RuntimePaths) -> Self {
        Self {
            supervisor: Arc::new(Mutex::new(SidecarSupervisor::new())),
            runtime_paths,
        }
    }

    pub fn supervisor(&self) -> Arc<Mutex<SidecarSupervisor>> {
        Arc::clone(&self.supervisor)
    }

    pub fn runtime_paths(&self) -> &RuntimePaths {
        &self.runtime_paths
    }

    pub fn attach_event_bridge(&self, app_handle: tauri::AppHandle) {
        let bridge: SidecarEventBridge = Arc::new(move |event| {
            let event_type = event.event_type.clone();
            let _ = app_handle.emit(event_type.as_str(), event);
        });
        if let Ok(mut supervisor) = self.supervisor.lock() {
            supervisor.set_event_bridge(bridge);
        }
    }
}

impl Default for AppState {
    fn default() -> Self {
        Self::new(RuntimePaths::for_current_process(RuntimeMode::Dev))
    }
}

fn build_context(context: Option<InvocationContext>) -> RpcContext {
    let context = context.unwrap_or_default();
    let parent_trace_id = context.parent_trace_id;
    let mut rpc_context = RpcContext::from_inputs(
        context.request_id,
        context.trace_id,
        context.session_id,
        context.deadline_ms,
    );
    rpc_context.parent_trace_id = parent_trace_id;
    rpc_context
}

fn required_string(value: Option<String>, field: &str) -> Result<String, RpcError> {
    value
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| RpcError::invalid_params(field))
}

fn required_object(value: Option<Value>, field: &str) -> Result<Value, RpcError> {
    match value {
        Some(value @ Value::Object(_)) => Ok(value),
        _ => Err(RpcError::invalid_params(field)),
    }
}

fn safe_optional_string(value: Option<String>) -> Option<String> {
    value.filter(|value| !value.trim().is_empty())
}

fn object_or_empty(value: Option<Value>) -> Value {
    match value {
        Some(value @ Value::Object(_)) => value,
        _ => json!({}),
    }
}

fn dispatch_bridge_command(
    state: &tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    method: &str,
    payload: Value,
    long_task: bool,
) -> Result<CommandResponse<Value>, RpcError> {
    let context = build_context(context);
    let mut supervisor = state.supervisor.lock().map_err(|_| RpcError::sidecar_not_ready())?;
    supervisor.configure_runtime_paths(state.runtime_paths());
    supervisor.dispatch_json_command(method, context, payload, long_task)
}

#[tauri::command]
fn sidecar_hello(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    _params: Option<EmptyParams>,
) -> Result<CommandResponse<HelloResult>, RpcError> {
    let context = build_context(context);
    let mut supervisor = state.supervisor.lock().map_err(|_| RpcError::sidecar_not_ready())?;
    supervisor.configure_runtime_paths(state.runtime_paths());
    supervisor.hello(context, state.runtime_paths())
}

#[tauri::command]
fn sidecar_health(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    _params: Option<EmptyParams>,
) -> Result<CommandResponse<HealthResult>, RpcError> {
    let context = build_context(context);
    let mut supervisor = state.supervisor.try_lock().map_err(|_| RpcError::sidecar_busy())?;
    supervisor.configure_runtime_paths(state.runtime_paths());
    supervisor.health(context)
}

#[tauri::command]
fn sidecar_cancel(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    params: Option<CancelParams>,
) -> Result<CommandResponse<CancelResult>, RpcError> {
    let context = build_context(context);
    let params = params.unwrap_or_default();
    let target_request_id = params
        .request_id
        .unwrap_or_else(|| context.request_id.clone());
    let mut supervisor = state.supervisor.try_lock().map_err(|_| RpcError::sidecar_busy())?;
    supervisor.configure_runtime_paths(state.runtime_paths());
    supervisor.cancel_with_reason(context, target_request_id, params.reason)
}

#[tauri::command]
fn sidecar_shutdown(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    _params: Option<EmptyParams>,
) -> Result<CommandResponse<ShutdownResult>, RpcError> {
    let context = build_context(context);
    let mut supervisor = state.supervisor.try_lock().map_err(|_| RpcError::sidecar_busy())?;
    supervisor.configure_runtime_paths(state.runtime_paths());
    supervisor.shutdown(context)
}

#[tauri::command]
fn config_get_all(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    params: Option<ScopeParams>,
) -> Result<CommandResponse<ConfigSnapshot>, RpcError> {
    let context = build_context(context);
    let scope = params.and_then(|params| params.scope);
    let mut supervisor = state.supervisor.lock().map_err(|_| RpcError::sidecar_not_ready())?;
    supervisor.configure_runtime_paths(state.runtime_paths());
    supervisor.config_get_all(context, scope)
}

#[tauri::command]
fn config_save_system(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    params: Option<ConfigSaveSystemParams>,
) -> Result<CommandResponse<Value>, RpcError> {
    let context = build_context(context);
    let params = params.unwrap_or_default();
    let draft = params.draft.or(params.snapshot).unwrap_or_else(|| json!({}));
    let payload = json!({
        "draft": draft,
        "base_version": params.base_version.unwrap_or(1),
        "confirm_token": params.confirm_token.unwrap_or_else(|| "settings-system-local".to_string()),
    });
    let mut supervisor = state.supervisor.lock().map_err(|_| RpcError::sidecar_not_ready())?;
    supervisor.configure_runtime_paths(state.runtime_paths());
    supervisor.dispatch_json_command("config.save_system", context, payload, false)
}

#[tauri::command]
fn logs_query(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    params: Option<LimitParams>,
) -> Result<CommandResponse<LogsQueryResult>, RpcError> {
    let context = build_context(context);
    let limit = params.and_then(|params| params.limit);
    let mut supervisor = state.supervisor.lock().map_err(|_| RpcError::sidecar_not_ready())?;
    supervisor.configure_runtime_paths(state.runtime_paths());
    supervisor.logs_query(context, limit)
}

#[tauri::command]
fn chat_send(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    params: Option<ChatSendParams>,
) -> Result<CommandResponse<Value>, RpcError> {
    let mut context = build_context(context);
    let params = params.unwrap_or_default();
    let params_session_id = params.session_id.clone().filter(|value| !value.trim().is_empty());
    if context
        .session_id
        .as_deref()
        .map(str::trim)
        .unwrap_or_default()
        .is_empty()
    {
        context.session_id = params_session_id.or_else(|| Some("default-session".to_string()));
    }
    let text = params.text.or(params.message).unwrap_or_default();
    let payload = json!({
        "text": text,
        "session_id": context.session_id.clone().unwrap_or_else(|| "default-session".to_string()),
        "visual_handle": params.visual_handle,
    });
    let mut supervisor = state.supervisor.lock().map_err(|_| RpcError::sidecar_not_ready())?;
    supervisor.configure_runtime_paths(state.runtime_paths());
    supervisor.dispatch_json_command("chat.send", context, payload, true)
}

#[tauri::command]
fn chat_retry(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    params: Option<ChatRetryParams>,
) -> Result<CommandResponse<Value>, RpcError> {
    let context = build_context(context);
    let params = params.unwrap_or_default();
    let source_request_id = params
        .source_request_id
        .or(params.request_id)
        .unwrap_or_default();
    let payload = json!({
        "source_request_id": source_request_id,
        "retry_policy": params.retry_policy,
    });
    let mut supervisor = state.supervisor.lock().map_err(|_| RpcError::sidecar_not_ready())?;
    supervisor.configure_runtime_paths(state.runtime_paths());
    supervisor.dispatch_json_command("chat.retry", context, payload, true)
}

#[tauri::command]
fn diagnostics_run(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    params: Option<DiagnosticsRunParams>,
) -> Result<CommandResponse<Value>, RpcError> {
    let context = build_context(context);
    let params = params.unwrap_or_default();
    let payload = json!({
        "checks": params.checks.unwrap_or_else(|| vec![
            "sidecar".to_string(),
            "config".to_string(),
            "logs".to_string(),
        ]),
        "include_sensitive": params.include_sensitive.unwrap_or(false),
    });
    let mut supervisor = state.supervisor.lock().map_err(|_| RpcError::sidecar_not_ready())?;
    supervisor.configure_runtime_paths(state.runtime_paths());
    supervisor.dispatch_json_command("diagnostics.run", context, payload, true)
}

#[tauri::command]
fn diagnostics_export(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    params: Option<DiagnosticsExportParams>,
) -> Result<CommandResponse<Value>, RpcError> {
    let context = build_context(context);
    let params = params.unwrap_or_default();
    let payload = json!({
        "report_handle": params.report_handle.unwrap_or_else(|| "report_latest".to_string()),
        "format": params.format.unwrap_or_else(|| "zip".to_string()),
    });
    let mut supervisor = state.supervisor.lock().map_err(|_| RpcError::sidecar_not_ready())?;
    supervisor.configure_runtime_paths(state.runtime_paths());
    supervisor.dispatch_json_command("diagnostics.export", context, payload, true)
}

#[tauri::command]
fn tools_list(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    params: Option<IncludeDisabledParams>,
) -> Result<CommandResponse<Value>, RpcError> {
    let params = params.unwrap_or_default();
    dispatch_bridge_command(
        &state,
        context,
        "tools.list",
        json!({ "include_disabled": params.include_disabled.unwrap_or(false) }),
        false,
    )
}

#[tauri::command]
fn tools_call(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    params: Option<ToolsCallParams>,
) -> Result<CommandResponse<Value>, RpcError> {
    let params = params.unwrap_or_default();
    let payload = json!({
        "tool_name": required_string(params.tool_name, "tool_name")?,
        "source": required_string(params.source, "source")?,
        "arguments": required_object(params.arguments, "arguments")?,
        "dry_run": params.dry_run.unwrap_or(true),
        "confirm_token": params.confirm_token,
    });
    dispatch_bridge_command(&state, context, "tools.call", payload, true)
}

#[tauri::command]
fn tools_audit_query(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    params: Option<AuditQueryParams>,
) -> Result<CommandResponse<Value>, RpcError> {
    let params = params.unwrap_or_default();
    let payload = json!({
        "limit": params.limit.unwrap_or(100).min(1000),
        "cursor": params.cursor,
        "filters": object_or_empty(params.filters),
    });
    dispatch_bridge_command(&state, context, "tools.audit_query", payload, false)
}

#[tauri::command]
fn plugins_status(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    params: Option<PluginStatusParams>,
) -> Result<CommandResponse<Value>, RpcError> {
    let params = params.unwrap_or_default();
    dispatch_bridge_command(
        &state,
        context,
        "plugins.status",
        json!({ "plugin_id": safe_optional_string(params.plugin_id) }),
        false,
    )
}

#[tauri::command]
fn plugins_refresh(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    params: Option<FiltersParams>,
) -> Result<CommandResponse<Value>, RpcError> {
    let params = params.unwrap_or_default();
    dispatch_bridge_command(
        &state,
        context,
        "plugins.refresh",
        json!({ "filters": object_or_empty(params.filters) }),
        true,
    )
}

#[tauri::command]
fn plugins_enable(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    params: Option<PluginToggleParams>,
) -> Result<CommandResponse<Value>, RpcError> {
    let params = params.unwrap_or_default();
    let payload = json!({
        "plugin_id": required_string(params.plugin_id, "plugin_id")?,
        "confirm_token": required_string(params.confirm_token, "confirm_token")?,
    });
    dispatch_bridge_command(&state, context, "plugins.enable", payload, false)
}

#[tauri::command]
fn plugins_disable(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    params: Option<PluginToggleParams>,
) -> Result<CommandResponse<Value>, RpcError> {
    let params = params.unwrap_or_default();
    dispatch_bridge_command(
        &state,
        context,
        "plugins.disable",
        json!({ "plugin_id": required_string(params.plugin_id, "plugin_id")? }),
        false,
    )
}

#[tauri::command]
fn mcp_list_servers(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    params: Option<IncludeDisabledParams>,
) -> Result<CommandResponse<Value>, RpcError> {
    let params = params.unwrap_or_default();
    dispatch_bridge_command(
        &state,
        context,
        "mcp.list_servers",
        json!({ "include_disabled": params.include_disabled.unwrap_or(false) }),
        false,
    )
}

#[tauri::command]
fn mcp_refresh(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    params: Option<McpRefreshParams>,
) -> Result<CommandResponse<Value>, RpcError> {
    let params = params.unwrap_or_default();
    dispatch_bridge_command(
        &state,
        context,
        "mcp.refresh",
        json!({ "server_id": safe_optional_string(params.server_id) }),
        true,
    )
}

#[tauri::command]
fn mcp_call_tool(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    params: Option<McpCallToolParams>,
) -> Result<CommandResponse<Value>, RpcError> {
    let params = params.unwrap_or_default();
    let payload = json!({
        "server_id": required_string(params.server_id, "server_id")?,
        "tool_name": required_string(params.tool_name, "tool_name")?,
        "arguments": required_object(params.arguments, "arguments")?,
        "confirm_token": params.confirm_token,
    });
    dispatch_bridge_command(&state, context, "mcp.call_tool", payload, true)
}

#[tauri::command]
fn security_list_grants(
    state: tauri::State<'_, AppState>,
    context: Option<InvocationContext>,
    params: Option<FiltersParams>,
) -> Result<CommandResponse<Value>, RpcError> {
    let params = params.unwrap_or_default();
    dispatch_bridge_command(
        &state,
        context,
        "security.list_grants",
        json!({ "filters": object_or_empty(params.filters) }),
        false,
    )
}

pub fn run() {
    tauri::Builder::default()
        .manage(AppState::default())
        .setup(|app| {
            let state = app.state::<AppState>();
            state.attach_event_bridge(app.handle().clone());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            sidecar_hello,
            sidecar_health,
            sidecar_cancel,
            sidecar_shutdown,
            config_get_all,
            config_save_system,
            logs_query,
            chat_send,
            chat_retry,
            diagnostics_run,
            diagnostics_export,
            tools_list,
            tools_call,
            tools_audit_query,
            plugins_status,
            plugins_refresh,
            plugins_enable,
            plugins_disable,
            mcp_list_servers,
            mcp_refresh,
            mcp_call_tool,
            security_list_grants
        ])
        .run(tauri::generate_context!())
        .expect("运行 Yumetsuki Tauri 桌面壳失败");
}
