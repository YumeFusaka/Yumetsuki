use std::collections::BTreeMap;
use std::env;
use std::io::{BufRead, BufReader, Read, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{mpsc, Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::rpc::{CommandResponse, EventEnvelope, RequestEnvelope, ResponseEnvelope, RpcContext, RpcError};
use crate::runtime_paths::RuntimePaths;

pub type SidecarEventBridge = Arc<dyn Fn(EventEnvelope<Value>) + Send + Sync + 'static>;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SidecarProcessSpec {
    pub program: String,
    pub args: Vec<String>,
    pub stdio_mode: String,
}

impl Default for SidecarProcessSpec {
    fn default() -> Self {
        Self {
            program: default_python_program(),
            args: vec![
                "-m".to_string(),
                "python_core.sidecar_main".to_string(),
                "--stdio".to_string(),
            ],
            stdio_mode: "jsonl-rpc".to_string(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SidecarProcessState {
    Running,
    ShuttingDown,
    Stopped,
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum RequestState {
    InFlight,
    Accepted,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct RequestRegistryEntry {
    method: String,
    state: RequestState,
    deadline_ms: u64,
    sidecar_generation: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HelloResult {
    pub selected_protocol_version: u16,
    pub min_compatible_protocol_version: u16,
    pub sidecar_version: String,
    pub capabilities: Vec<String>,
    pub runtime_paths_ready: bool,
    pub schema_hash: String,
    pub sidecar_generation: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HealthResult {
    pub status: String,
    pub uptime_ms: u128,
    pub active_task_count: usize,
    pub sidecar_generation: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CancelResult {
    pub target_request_id: String,
    pub status: String,
    pub terminal_state: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ShutdownResult {
    pub accepted_shutdown: bool,
    pub sidecar_generation: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConfigSnapshot {
    pub scope: String,
    pub redacted: bool,
    pub values: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct LogEntry {
    pub level: String,
    pub source: String,
    pub message: String,
    pub trace_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct LogsQueryResult {
    pub entries: Vec<LogEntry>,
    pub limit: usize,
    pub next_cursor: Option<String>,
}

struct ManagedProcess {
    child: Child,
    stdin: Arc<Mutex<ChildStdin>>,
}

#[derive(Clone)]
struct SharedRuntime {
    request_registry: BTreeMap<String, RequestRegistryEntry>,
    waiters: BTreeMap<String, mpsc::Sender<Result<ResponseEnvelope<Value>, RpcError>>>,
    pending_events: BTreeMap<String, Vec<EventEnvelope<Value>>>,
    event_bridge: Option<SidecarEventBridge>,
}

impl SharedRuntime {
    fn new() -> Self {
        Self {
            request_registry: BTreeMap::new(),
            waiters: BTreeMap::new(),
            pending_events: BTreeMap::new(),
            event_bridge: None,
        }
    }
}

pub struct SidecarSupervisor {
    started_at: Instant,
    generation: u64,
    has_started: bool,
    shutdown_requested: bool,
    process_spec: SidecarProcessSpec,
    process_state: SidecarProcessState,
    request_deadline_ms: u64,
    shutdown_timeout_ms: u64,
    runtime_paths: Option<RuntimePaths>,
    shared: Arc<Mutex<SharedRuntime>>,
    process: Option<ManagedProcess>,
}

impl Default for SidecarSupervisor {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for SidecarSupervisor {
    fn drop(&mut self) {
        let _ = self.stop_child(Duration::from_millis(100));
    }
}

impl SidecarSupervisor {
    pub fn new() -> Self {
        Self {
            started_at: Instant::now(),
            generation: 1,
            has_started: false,
            shutdown_requested: false,
            process_spec: SidecarProcessSpec::default(),
            process_state: SidecarProcessState::Stopped,
            request_deadline_ms: 30_000,
            shutdown_timeout_ms: 5_000,
            runtime_paths: None,
            shared: Arc::new(Mutex::new(SharedRuntime::new())),
            process: None,
        }
    }

    pub fn generation(&self) -> u64 {
        self.generation
    }

    pub fn configure_runtime_paths(&mut self, runtime_paths: &RuntimePaths) {
        if self.runtime_paths.is_none() {
            self.runtime_paths = Some(runtime_paths.clone());
        }
    }

    pub fn set_event_bridge(&mut self, bridge: SidecarEventBridge) {
        if let Ok(mut shared) = self.shared.lock() {
            shared.event_bridge = Some(bridge);
        }
    }

    pub fn hello(
        &mut self,
        context: RpcContext,
        runtime_paths: &RuntimePaths,
    ) -> Result<CommandResponse<HelloResult>, RpcError> {
        self.runtime_paths = Some(runtime_paths.clone());
        self.ensure_child_started(true, runtime_paths)?;
        let response = self.dispatch_value(
            "sidecar.hello",
            context.clone(),
            serde_json::json!({
                "supported_protocol_versions": [context.protocol_version],
                "capabilities": [],
                "frontend_version": ""
            }),
            false,
        )?;
        if !response.ok {
            return Err(response
                .error
                .unwrap_or_else(|| self.invalid_python_response("sidecar.hello", "missing error")));
        }
        let result = response
            .result
            .ok_or_else(|| self.invalid_python_response("sidecar.hello", "missing result"))?;
        let hello = HelloResult {
            selected_protocol_version: value_u16(&result, "selected_protocol_version")?,
            min_compatible_protocol_version: value_u16(&result, "min_compatible_protocol_version")?,
            sidecar_version: value_string(&result, "sidecar_version")?,
            capabilities: value_string_list(&result, "capabilities")?,
            runtime_paths_ready: value_bool(&result, "runtime_paths_ready")?,
            schema_hash: value_string(&result, "schema_hash")?,
            sidecar_generation: self.generation,
        };
        Ok(CommandResponse::done(&context, hello))
    }

    pub fn health(&mut self, context: RpcContext) -> Result<CommandResponse<HealthResult>, RpcError> {
        self.ensure_runtime_paths()?;
        if !self.shutdown_requested {
            let runtime_paths = self
                .runtime_paths
                .clone()
                .ok_or_else(RpcError::sidecar_not_ready)?;
            self.ensure_child_started(false, &runtime_paths)?;
        }
        let response = if self.shutdown_requested {
            None
        } else {
            Some(self.dispatch_value(
                "sidecar.health",
                context.clone(),
                serde_json::json!({ "include_tasks": true }),
                false,
            )?)
        };

        let status = if self.shutdown_requested || matches!(self.process_state, SidecarProcessState::ShuttingDown) {
            "shutting_down".to_string()
        } else if self.process.is_some() {
            "healthy".to_string()
        } else {
            "not_ready".to_string()
        };

        let active_task_count = response
            .as_ref()
            .and_then(|frame| frame.result.as_ref())
            .and_then(|result| value_usize(result, "active_task_count").ok())
            .unwrap_or_else(|| self.active_task_count());
        let uptime_ms = response
            .as_ref()
            .and_then(|frame| frame.result.as_ref())
            .and_then(|result| value_u128(result, "uptime_ms").ok())
            .unwrap_or_else(|| self.started_at.elapsed().as_millis());

        Ok(CommandResponse::done(
            &context,
            HealthResult {
                status,
                uptime_ms,
                active_task_count,
                sidecar_generation: self.generation,
            },
        ))
    }

    pub fn cancel(
        &mut self,
        context: RpcContext,
        target_request_id: String,
    ) -> Result<CommandResponse<CancelResult>, RpcError> {
        self.cancel_with_reason(context, target_request_id, None)
    }

    pub fn cancel_with_reason(
        &mut self,
        context: RpcContext,
        target_request_id: String,
        reason: Option<String>,
    ) -> Result<CommandResponse<CancelResult>, RpcError> {
        self.ensure_runtime_paths()?;
        if self.shutdown_requested {
            return Err(RpcError::sidecar_not_ready());
        }
        let runtime_paths = self.runtime_paths.clone().ok_or_else(RpcError::sidecar_not_ready)?;
        self.ensure_child_started(false, &runtime_paths)?;
        let target_request_id_for_result = target_request_id.clone();
        let response = self.dispatch_value(
            "sidecar.cancel",
            context.clone(),
            serde_json::json!({
                "request_id": target_request_id,
                "reason": reason.unwrap_or_default()
            }),
            false,
        )?;
        if !response.ok {
            return Err(response
                .error
                .unwrap_or_else(|| self.invalid_python_response("sidecar.cancel", "missing error")));
        }
        let result = response
            .result
            .ok_or_else(|| self.invalid_python_response("sidecar.cancel", "missing result"))?;
        let cancel = CancelResult {
            target_request_id: value_string(&result, "target_request_id")
                .unwrap_or(target_request_id_for_result),
            status: value_string(&result, "status")?,
            terminal_state: value_string(&result, "terminal_state")?,
        };
        Ok(CommandResponse::accepted(&context, cancel))
    }

    pub fn shutdown(
        &mut self,
        context: RpcContext,
    ) -> Result<CommandResponse<ShutdownResult>, RpcError> {
        self.ensure_runtime_paths()?;
        let runtime_paths = self.runtime_paths.clone().ok_or_else(RpcError::sidecar_not_ready)?;
        self.ensure_child_started(false, &runtime_paths)?;
        let response = self.dispatch_value(
            "sidecar.shutdown",
            context.clone(),
            serde_json::json!({ "reason": "tauri", "deadline_ms": self.shutdown_timeout_ms }),
            true,
        )?;
        if !response.ok {
            return Err(response
                .error
                .unwrap_or_else(|| self.invalid_python_response("sidecar.shutdown", "missing error")));
        }
        self.shutdown_requested = true;
        self.process_state = SidecarProcessState::ShuttingDown;
        let _ = self.stop_child(Duration::from_millis(self.shutdown_timeout_ms));

        let result = response
            .result
            .ok_or_else(|| self.invalid_python_response("sidecar.shutdown", "missing result"))?;
        let shutdown = ShutdownResult {
            accepted_shutdown: value_bool(&result, "accepted_shutdown")?,
            sidecar_generation: self.generation,
        };
        Ok(CommandResponse::accepted(&context, shutdown))
    }

    pub fn config_get_all(
        &mut self,
        context: RpcContext,
        scope: Option<String>,
    ) -> Result<CommandResponse<ConfigSnapshot>, RpcError> {
        self.ensure_runtime_paths()?;
        if self.shutdown_requested {
            return Err(RpcError::sidecar_not_ready());
        }
        let runtime_paths = self.runtime_paths.clone().ok_or_else(RpcError::sidecar_not_ready)?;
        self.ensure_child_started(false, &runtime_paths)?;
        let response = self.dispatch_value(
            "config.get_all",
            context.clone(),
            serde_json::json!({ "scope": scope.clone().unwrap_or_else(|| "all".to_string()) }),
            false,
        )?;
        if !response.ok {
            return Err(response
                .error
                .unwrap_or_else(|| self.invalid_python_response("config.get_all", "missing error")));
        }
        let result = response
            .result
            .ok_or_else(|| self.invalid_python_response("config.get_all", "missing result"))?;
        let snapshot = ConfigSnapshot {
            scope: scope.unwrap_or_else(|| value_string(&result, "scope").unwrap_or_else(|_| "all".to_string())),
            redacted: true,
            values: config_values_from_python(&result)?,
        };
        Ok(CommandResponse::done(&context, snapshot))
    }

    pub fn logs_query(
        &mut self,
        context: RpcContext,
        limit: Option<usize>,
    ) -> Result<CommandResponse<LogsQueryResult>, RpcError> {
        self.ensure_runtime_paths()?;
        if self.shutdown_requested {
            return Err(RpcError::sidecar_not_ready());
        }
        let runtime_paths = self.runtime_paths.clone().ok_or_else(RpcError::sidecar_not_ready)?;
        self.ensure_child_started(false, &runtime_paths)?;
        let limit = limit.unwrap_or(100).min(500);
        let response = self.dispatch_value(
            "logs.query",
            context.clone(),
            serde_json::json!({ "limit": limit, "channel": "all" }),
            false,
        )?;
        if !response.ok {
            return Err(response
                .error
                .unwrap_or_else(|| self.invalid_python_response("logs.query", "missing error")));
        }
        let result = response
            .result
            .ok_or_else(|| self.invalid_python_response("logs.query", "missing result"))?;
        let entries = result
            .get("items")
            .and_then(Value::as_array)
            .map(|items| {
                items
                    .iter()
                    .map(|item| LogEntry {
                        level: value_string(item, "level").unwrap_or_else(|_| "info".to_string()),
                        source: value_string(item, "source").unwrap_or_else(|_| "python_core.sidecar".to_string()),
                        message: value_string(item, "message").unwrap_or_else(|_| String::new()),
                        trace_id: value_string(item, "trace_id").unwrap_or_else(|_| context.trace_id.clone()),
                    })
                    .collect::<Vec<_>>()
            })
            .unwrap_or_default();
        let next_cursor = result.get("next_cursor").and_then(Value::as_str).map(ToOwned::to_owned);
        Ok(CommandResponse::done(
            &context,
            LogsQueryResult {
                entries,
                limit,
                next_cursor,
            },
        ))
    }

    pub fn dispatch_json_command(
        &mut self,
        method: &str,
        context: RpcContext,
        params: Value,
        long_task: bool,
    ) -> Result<CommandResponse<Value>, RpcError> {
        self.ensure_runtime_paths()?;
        if self.shutdown_requested {
            return Err(RpcError::sidecar_not_ready());
        }
        let runtime_paths = self.runtime_paths.clone().ok_or_else(RpcError::sidecar_not_ready)?;
        self.ensure_child_started(false, &runtime_paths)?;
        let response = self.dispatch_value(method, context.clone(), params, long_task)?;
        if !response.ok {
            return Err(response
                .error
                .unwrap_or_else(|| self.invalid_python_response(method, "missing error")));
        }
        let result = response
            .result
            .ok_or_else(|| self.invalid_python_response(method, "missing result"))?;
        if long_task {
            Ok(CommandResponse::accepted(&context, result))
        } else {
            Ok(CommandResponse::done(&context, result))
        }
    }

    fn ensure_runtime_paths(&self) -> Result<(), RpcError> {
        if self.runtime_paths.is_none() {
            Err(RpcError::sidecar_not_ready())
        } else {
            Ok(())
        }
    }

    fn ensure_child_started(&mut self, allow_restart_after_shutdown: bool, runtime_paths: &RuntimePaths) -> Result<(), RpcError> {
        if self.shutdown_requested && !allow_restart_after_shutdown {
            return Err(RpcError::sidecar_not_ready());
        }
        if self.shutdown_requested && allow_restart_after_shutdown {
            let _ = self.stop_child(Duration::from_millis(self.shutdown_timeout_ms));
            self.shutdown_requested = false;
            self.process_state = SidecarProcessState::Stopped;
        }

        if self.process.is_some() {
            if self.child_exited()? {
                self.process = None;
                self.process_state = SidecarProcessState::Stopped;
            } else {
                return Ok(());
            }
        }

        let restarting = self.has_started;
        if restarting {
            self.fail_all_pending(RpcError::sidecar_restarted());
            self.generation += 1;
            if !self.shutdown_requested {
                self.emit_system_event("sidecar.restarted", serde_json::json!({ "generation": self.generation }));
            }
        }

        self.start_child(runtime_paths)?;
        self.has_started = true;
        self.shutdown_requested = false;
        self.process_state = SidecarProcessState::Running;
        self.started_at = Instant::now();
        Ok(())
    }

    fn start_child(&mut self, runtime_paths: &RuntimePaths) -> Result<(), RpcError> {
        let runtime_paths_json = serde_json::to_string(&runtime_paths.to_injected_json()).map_err(|err| {
            RpcError::new(
                "rpc.invalid_params",
                "运行期路径序列化失败",
                "运行期路径无法注入 Python 内核。",
                false,
                serde_json::json!({ "summary": err.to_string() }),
            )
        })?;
        let repo_root = find_repo_root();
        let mut command = Command::new(&self.process_spec.program);
        command
            .args(&self.process_spec.args)
            .arg("--runtime-paths-json")
            .arg(runtime_paths_json)
            .current_dir(repo_root)
            .env("PYTHONUNBUFFERED", "1")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        let mut child = command.spawn().map_err(|err| {
            RpcError::new(
                "sidecar.not_ready",
                "无法启动 Python sidecar",
                "Python 内核启动失败。",
                true,
                serde_json::json!({ "summary": err.to_string() }),
            )
        })?;

        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| self.spawn_failure("stdin 不可用"))?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| self.spawn_failure("stdout 不可用"))?;
        let stderr = child
            .stderr
            .take()
            .ok_or_else(|| self.spawn_failure("stderr 不可用"))?;

        let shared = Arc::clone(&self.shared);
        thread::spawn(move || read_stdout_loop(stdout, shared));

        thread::spawn(move || read_stderr_loop(stderr));

        self.process = Some(ManagedProcess {
            child,
            stdin: Arc::new(Mutex::new(stdin)),
        });
        Ok(())
    }

    fn dispatch_value(
        &mut self,
        method: &str,
        context: RpcContext,
        params: Value,
        retain_after_response: bool,
    ) -> Result<ResponseEnvelope<Value>, RpcError> {
        self.ensure_runtime_paths()?;
        let deadline_ms = if context.deadline_ms == 0 {
            self.request_deadline_ms
        } else {
            context.deadline_ms
        };
        let request = RequestEnvelope {
            kind: "request".to_string(),
            request_id: context.request_id.clone(),
            method: method.to_string(),
            params,
            protocol_version: context.protocol_version,
            trace_id: context.trace_id.clone(),
            parent_trace_id: context.parent_trace_id.clone(),
            session_id: Some(context.session_id.clone().unwrap_or_default()),
            deadline_ms,
        };
        let (tx, rx) = mpsc::channel();
        {
            let mut shared = self.shared.lock().map_err(|_| RpcError::sidecar_not_ready())?;
            shared.waiters.insert(context.request_id.clone(), tx);
            shared.request_registry.insert(
                context.request_id.clone(),
                RequestRegistryEntry {
                    method: method.to_string(),
                    state: RequestState::InFlight,
                    deadline_ms,
                    sidecar_generation: self.generation,
                },
            );
        }

        let payload = serde_json::to_vec(&request).map_err(|err| self.invalid_request_error(method, err.to_string()))?;
        if let Err(err) = payload_write(self.process_stdin()?, &payload) {
            self.clear_request(&context.request_id);
            return Err(err);
        }

        let frame = rx
            .recv_timeout(Duration::from_millis(deadline_ms))
            .map_err(|_| {
                self.clear_request(&context.request_id);
                RpcError::request_timeout(&context.request_id, deadline_ms)
            })??;

        if frame.ok {
            if retain_after_response {
                self.mark_request_accepted_and_flush_events(&context.request_id)?;
            } else {
                self.clear_request(&context.request_id);
            }
        } else {
            self.clear_request(&context.request_id);
        }

        Ok(frame)
    }

    fn process_stdin(&self) -> Result<Arc<Mutex<ChildStdin>>, RpcError> {
        let process = self
            .process
            .as_ref()
            .ok_or_else(RpcError::sidecar_not_ready)?;
        Ok(Arc::clone(&process.stdin))
    }

    fn child_exited(&mut self) -> Result<bool, RpcError> {
        let exited = if let Some(process) = self.process.as_mut() {
            match process.child.try_wait() {
                Ok(Some(status)) => {
                    if !self.shutdown_requested {
                        self.fail_all_pending(RpcError::sidecar_restarted());
                        self.emit_system_event(
                            "sidecar.crashed",
                            serde_json::json!({
                                "status": status.code().unwrap_or_default(),
                                "generation": self.generation,
                            }),
                        );
                    }
                    true
                }
                Ok(None) => false,
                Err(err) => {
                    return Err(RpcError::new(
                        "sidecar.not_ready",
                        "检查 Python sidecar 状态失败",
                        "Python 内核状态检查失败。",
                        true,
                        serde_json::json!({ "summary": err.to_string() }),
                    ));
                }
            }
        } else {
            true
        };
        if exited {
            self.process = None;
            self.process_state = SidecarProcessState::Stopped;
        }
        Ok(exited)
    }

    fn stop_child(&mut self, timeout: Duration) -> Result<(), RpcError> {
        let Some(mut process) = self.process.take() else {
            self.process_state = SidecarProcessState::Stopped;
            return Ok(());
        };
        let start = Instant::now();
        loop {
            match process.child.try_wait() {
                Ok(Some(_status)) => {
                    self.process_state = SidecarProcessState::Stopped;
                    return Ok(());
                }
                Ok(None) if start.elapsed() >= timeout => {
                    let _ = process.child.kill();
                    let _ = process.child.wait();
                    self.process_state = SidecarProcessState::Stopped;
                    return Ok(());
                }
                Ok(None) => thread::sleep(Duration::from_millis(20)),
                Err(err) => {
                    self.process_state = SidecarProcessState::Stopped;
                    return Err(RpcError::new(
                        "sidecar.not_ready",
                        "关闭 Python sidecar 失败",
                        "Python 内核关闭失败。",
                        true,
                        serde_json::json!({ "summary": err.to_string() }),
                    ));
                }
            }
        }
    }

    fn clear_request(&self, request_id: &str) {
        if let Ok(mut shared) = self.shared.lock() {
            shared.waiters.remove(request_id);
            shared.request_registry.remove(request_id);
            shared.pending_events.remove(request_id);
        }
    }

    fn mark_request_accepted_and_flush_events(&self, request_id: &str) -> Result<(), RpcError> {
        let (events, event_bridge) = {
            let mut shared = self.shared.lock().map_err(|_| RpcError::sidecar_not_ready())?;
            if let Some(entry) = shared.request_registry.get_mut(request_id) {
                entry.state = RequestState::Accepted;
            }
            let events = shared.pending_events.remove(request_id).unwrap_or_default();
            if events
                .iter()
                .any(|event| event.event_type == "sidecar.exiting" || is_terminal_event(&event.event_type))
            {
                shared.request_registry.remove(request_id);
            }
            (events, shared.event_bridge.clone())
        };

        if let Some(bridge) = event_bridge {
            for event in events {
                bridge(event);
            }
        }
        Ok(())
    }

    fn fail_all_pending(&self, error: RpcError) {
        let waiters = {
            let Ok(mut shared) = self.shared.lock() else {
                return;
            };
            let waiters = std::mem::take(&mut shared.waiters);
            shared.request_registry.clear();
            shared.pending_events.clear();
            waiters
        };

        for waiter in waiters.into_values() {
            let _ = waiter.send(Err(error.clone()));
        }
    }

    fn emit_system_event(&self, event_type: &str, payload: Value) {
        let event_bridge = self
            .shared
            .lock()
            .ok()
            .and_then(|shared| shared.event_bridge.clone());
        if let Some(bridge) = event_bridge {
            bridge(EventEnvelope {
                kind: "event".to_string(),
                event_type: event_type.to_string(),
                request_id: "sidecar.system".to_string(),
                protocol_version: 1,
                trace_id: format!("trace_sidecar_{}", self.generation),
                parent_trace_id: None,
                session_id: None,
                sequence: 1,
                timestamp_ms: now_ms(),
                payload,
            });
        }
    }

    fn invalid_python_response(&self, method: &str, reason: &str) -> RpcError {
        RpcError::new(
            "rpc.invalid_frame",
            format!("Python sidecar 返回无效响应: {method}"),
            "Python 内核返回的数据格式错误。",
            true,
            serde_json::json!({ "method": method, "reason": reason }),
        )
    }

    fn invalid_request_error(&self, method: &str, summary: String) -> RpcError {
        RpcError::new(
            "rpc.invalid_params",
            format!("无法构造请求: {method}"),
            "请求参数无法发送到 Python 内核。",
            false,
            serde_json::json!({ "method": method, "summary": summary }),
        )
    }

    fn spawn_failure(&self, summary: &str) -> RpcError {
        RpcError::new(
            "sidecar.not_ready",
            "启动 Python sidecar 失败",
            "Python 内核启动失败。",
            true,
            serde_json::json!({ "summary": summary }),
        )
    }

    fn active_task_count(&self) -> usize {
        self.shared
            .lock()
            .map(|shared| {
                shared
                    .request_registry
                    .values()
                    .filter(|entry| matches!(entry.state, RequestState::Accepted))
                    .count()
            })
            .unwrap_or(0)
    }
}

fn read_stdout_loop(stdout: impl Read + Send + 'static, shared: Arc<Mutex<SharedRuntime>>) {
    let reader = BufReader::new(stdout);
    for line in reader.lines() {
        let Ok(line) = line else {
            break;
        };
        if line.trim().is_empty() {
            continue;
        }
        let Ok(raw) = serde_json::from_str::<Value>(&line) else {
            continue;
        };
        let kind = raw.get("kind").and_then(Value::as_str).unwrap_or_default();
        match kind {
            "response" => {
                if let Ok(frame) = serde_json::from_value::<ResponseEnvelope<Value>>(raw) {
                    if let Ok(mut shared) = shared.lock() {
                        if let Some(waiter) = shared.waiters.remove(&frame.request_id) {
                            let _ = waiter.send(Ok(frame));
                        }
                    }
                }
            }
            "event" => {
                if let Ok(frame) = serde_json::from_value::<EventEnvelope<Value>>(raw) {
                    let (event_bridge, buffered) = {
                        let mut shared = match shared.lock() {
                            Ok(shared) => shared,
                            Err(_) => continue,
                        };
                        let should_buffer = shared
                            .request_registry
                            .get(&frame.request_id)
                            .map(|entry| matches!(entry.state, RequestState::InFlight))
                            .unwrap_or(false);
                        if should_buffer {
                            shared
                                .pending_events
                                .entry(frame.request_id.clone())
                                .or_default()
                                .push(frame.clone());
                            (None, true)
                        } else {
                            if frame.event_type == "sidecar.exiting" || is_terminal_event(&frame.event_type) {
                                shared.request_registry.remove(&frame.request_id);
                            }
                            (shared.event_bridge.clone(), false)
                        }
                    };
                    if buffered {
                        continue;
                    }
                    if let Some(bridge) = event_bridge {
                        bridge(frame);
                    }
                }
            }
            _ => {}
        }
    }
}

fn read_stderr_loop(stderr: impl Read + Send + 'static) {
    let reader = BufReader::new(stderr);
    for line in reader.lines() {
        let Ok(line) = line else {
            break;
        };
        if line.trim().is_empty() {
            continue;
        }
        eprintln!("{}", sanitize_stderr_line(&line));
    }
}

fn sanitize_stderr_line(line: &str) -> String {
    let lower = line.to_ascii_lowercase();
    let sensitive_markers = [
        "api_key",
        "apikey",
        "authorization",
        "bearer ",
        "cookie",
        "password",
        "secret",
        "token",
        "sk-",
    ];
    let path_markers = ["\\users\\", "/users/", "\\project\\yumetsuki", "/project/yumetsuki"];
    if sensitive_markers.iter().any(|marker| lower.contains(marker))
        || path_markers.iter().any(|marker| lower.contains(marker))
        || contains_private_url(&lower)
    {
        return "[sidecar.stderr.redacted]".to_string();
    }

    const MAX_STDERR_CHARS: usize = 500;
    if line.chars().count() > MAX_STDERR_CHARS {
        let mut truncated = line.chars().take(MAX_STDERR_CHARS).collect::<String>();
        truncated.push_str("...[truncated]");
        truncated
    } else {
        line.to_string()
    }
}

fn contains_private_url(lower: &str) -> bool {
    let direct_markers = [
        "http://localhost",
        "https://localhost",
        "http://127.",
        "https://127.",
        "http://10.",
        "https://10.",
        "http://192.168.",
        "https://192.168.",
    ];
    if direct_markers.iter().any(|marker| lower.contains(marker)) {
        return true;
    }
    (16..=31).any(|octet| {
        lower.contains(&format!("http://172.{octet}."))
            || lower.contains(&format!("https://172.{octet}."))
    })
}

fn payload_write(stdin: Arc<Mutex<ChildStdin>>, payload: &[u8]) -> Result<(), RpcError> {
    let mut guard = stdin.lock().map_err(|_| RpcError::sidecar_not_ready())?;
    guard.write_all(payload).map_err(|err| {
        RpcError::new(
            "sidecar.not_ready",
            "写入 Python sidecar 失败",
            "无法与 Python 内核通信。",
            true,
            serde_json::json!({ "summary": err.to_string() }),
        )
    })?;
    guard.write_all(b"\n").map_err(|err| {
        RpcError::new(
            "sidecar.not_ready",
            "写入 Python sidecar 失败",
            "无法与 Python 内核通信。",
            true,
            serde_json::json!({ "summary": err.to_string() }),
        )
    })?;
    guard.flush().map_err(|err| {
        RpcError::new(
            "sidecar.not_ready",
            "刷新 Python sidecar 失败",
            "无法与 Python 内核通信。",
            true,
            serde_json::json!({ "summary": err.to_string() }),
        )
    })?;
    Ok(())
}

fn is_terminal_event(event_type: &str) -> bool {
    event_type.ends_with(".done")
        || event_type.ends_with(".error")
        || event_type.ends_with(".cancelled")
        || matches!(event_type, "tool.result" | "mcp.tool_done")
}

fn config_values_from_python(result: &Value) -> Result<BTreeMap<String, String>, RpcError> {
    let snapshot = result
        .get("redacted_snapshot")
        .and_then(Value::as_object)
        .ok_or_else(|| RpcError::new(
            "rpc.invalid_frame",
            "Python sidecar 返回的配置快照缺少 redacted_snapshot",
            "配置查询返回的数据格式错误。",
            true,
            serde_json::json!({}),
        ))?;
    let mut values = BTreeMap::new();
    if let Some(system) = snapshot.get("system").and_then(Value::as_object) {
        for (key, value) in system {
            values.insert(format!("system.{key}"), value_to_string(value));
        }
    }
    if let Some(api) = snapshot.get("api").and_then(Value::as_object) {
        for (key, value) in api {
            values.insert(format!("api.{key}"), value_to_string(value));
        }
    }
    if let Some(memory) = snapshot.get("memory").and_then(Value::as_object) {
        for (key, value) in memory {
            values.insert(format!("memory.{key}"), value_to_string(value));
        }
    }
    values.insert(
        "version".to_string(),
        value_u64(result, "version")?.to_string(),
    );
    Ok(values)
}

fn value_string(value: &Value, key: &str) -> Result<String, RpcError> {
    value
        .get(key)
        .and_then(Value::as_str)
        .map(ToOwned::to_owned)
        .ok_or_else(|| {
            RpcError::new(
                "rpc.invalid_frame",
                format!("字段 {key} 缺失或类型错误"),
                "Python 内核返回的数据格式错误。",
                true,
                serde_json::json!({ "field": key }),
            )
        })
}

fn value_string_list(value: &Value, key: &str) -> Result<Vec<String>, RpcError> {
    let items = value
        .get(key)
        .and_then(Value::as_array)
        .ok_or_else(|| {
            RpcError::new(
                "rpc.invalid_frame",
                format!("字段 {key} 缺失或类型错误"),
                "Python 内核返回的数据格式错误。",
                true,
                serde_json::json!({ "field": key }),
            )
        })?;
    Ok(items
        .iter()
        .filter_map(Value::as_str)
        .map(ToOwned::to_owned)
        .collect())
}

fn value_bool(value: &Value, key: &str) -> Result<bool, RpcError> {
    value
        .get(key)
        .and_then(Value::as_bool)
        .ok_or_else(|| invalid_field(key))
}

fn value_u16(value: &Value, key: &str) -> Result<u16, RpcError> {
    value
        .get(key)
        .and_then(Value::as_u64)
        .and_then(|number| u16::try_from(number).ok())
        .ok_or_else(|| invalid_field(key))
}

fn value_u64(value: &Value, key: &str) -> Result<u64, RpcError> {
    value
        .get(key)
        .and_then(Value::as_u64)
        .ok_or_else(|| invalid_field(key))
}

fn value_usize(value: &Value, key: &str) -> Result<usize, RpcError> {
    value
        .get(key)
        .and_then(Value::as_u64)
        .and_then(|number| usize::try_from(number).ok())
        .ok_or_else(|| invalid_field(key))
}

fn value_u128(value: &Value, key: &str) -> Result<u128, RpcError> {
    value
        .get(key)
        .and_then(Value::as_u64)
        .map(u128::from)
        .ok_or_else(|| invalid_field(key))
}

fn invalid_field(key: &str) -> RpcError {
    RpcError::new(
        "rpc.invalid_frame",
        format!("字段 {key} 缺失或类型错误"),
        "Python 内核返回的数据格式错误。",
        true,
        serde_json::json!({ "field": key }),
    )
}

fn value_to_string(value: &Value) -> String {
    value
        .as_str()
        .map(ToOwned::to_owned)
        .unwrap_or_else(|| value.to_string())
}

fn default_python_program() -> String {
    env::var("YUMETSUKI_PYTHON")
        .or_else(|_| env::var("PYTHON"))
        .unwrap_or_else(|_| "python".to_string())
}

fn find_repo_root() -> PathBuf {
    let mut candidates = Vec::new();
    if let Ok(current) = env::current_dir() {
        candidates.push(current);
    }
    candidates.push(PathBuf::from(env!("CARGO_MANIFEST_DIR")));
    for base in candidates {
        for ancestor in base.ancestors() {
            if ancestor.join("python_core").join("sidecar_main.py").exists() {
                return ancestor.to_path_buf();
            }
        }
    }
    env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

fn now_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::{contains_private_url, is_terminal_event, sanitize_stderr_line};

    #[test]
    fn stderr_sanitizer_redacts_sensitive_values_paths_and_private_urls() {
        assert_eq!(sanitize_stderr_line("api_key=sk-secret"), "[sidecar.stderr.redacted]");
        assert_eq!(
            sanitize_stderr_line("loading C:/Users/alice/private/model.bin"),
            "[sidecar.stderr.redacted]"
        );
        assert_eq!(
            sanitize_stderr_line("request http://127.0.0.1:8080/secret?q=1"),
            "[sidecar.stderr.redacted]"
        );
        assert_eq!(
            sanitize_stderr_line("request https://10.0.0.5/internal"),
            "[sidecar.stderr.redacted]"
        );
        assert_eq!(
            sanitize_stderr_line("request http://172.20.1.5/internal"),
            "[sidecar.stderr.redacted]"
        );
        assert_eq!(
            sanitize_stderr_line("request https://192.168.1.2/internal"),
            "[sidecar.stderr.redacted]"
        );
    }

    #[test]
    fn private_url_detector_leaves_public_urls_alone() {
        assert!(contains_private_url("see http://localhost:8080"));
        assert!(contains_private_url("see https://172.31.0.1/status"));
        assert!(!contains_private_url("see https://example.com/status"));
        assert!(!contains_private_url("see https://172.32.0.1/status"));
    }

    #[test]
    fn phase4_result_events_are_terminal() {
        assert!(is_terminal_event("tool.result"));
        assert!(is_terminal_event("mcp.tool_done"));
        assert!(is_terminal_event("plugin.done"));
        assert!(!is_terminal_event("tool.audit"));
        assert!(!is_terminal_event("mcp.tool_started"));
    }
}
