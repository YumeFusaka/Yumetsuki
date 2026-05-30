use std::collections::HashMap;
use std::io::Write;
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

use crate::rpc::{RequestEnvelope, ResponseEnvelope};
use crate::runtime_paths::RuntimePaths;

pub struct SidecarSupervisor {
    child: Child,
    repo_root: std::path::PathBuf,
    registry: RequestRegistry,
    generation: u64,
    next_request: u64,
    degraded: bool,
}

#[derive(Debug, Clone)]
pub struct RestartedRequest {
    pub request_id: String,
    pub error_code: String,
}

pub struct RequestRegistry {
    generation: u64,
    pending: HashMap<String, Instant>,
}

impl SidecarSupervisor {
    pub fn spawn_dev(repo_root: std::path::PathBuf) -> Result<Self, String> {
        let runtime_paths = RuntimePaths::for_dev_repo(repo_root.clone())?;
        let mut child = Command::new(python_executable())
            .arg("-u")
            .arg("-m")
            .arg("python_core.sidecar_main")
            .arg("--stdio")
            .arg("--runtime-paths-json")
            .arg(runtime_paths.to_json())
            .current_dir(&repo_root)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|error| format!("spawn sidecar failed: {error}"))?;

        // Phase 1.3 keeps a long-lived child for lifecycle semantics. Actual request
        // round trips use one-shot stdio to avoid leaking waiters while the async
        // transport is still being hardened.
        child.stdin.take();
        child.stdout.take();
        child.stderr.take();

        Ok(Self {
            child,
            repo_root,
            registry: RequestRegistry::new(1),
            generation: 1,
            next_request: 1,
            degraded: false,
        })
    }

    pub fn generation(&self) -> u64 {
        self.generation
    }

    pub fn is_degraded(&self) -> bool {
        self.degraded
    }

    pub fn request(&mut self, method: &str, params_json: &str, deadline_ms: u64) -> Result<ResponseEnvelope, String> {
        if self.child.try_wait().map_err(|error| error.to_string())?.is_some() {
            self.degraded = true;
            self.registry.mark_restarted();
            return Ok(ResponseEnvelope::synthetic_error("sidecar.restarted"));
        }
        let request_id = format!("rust_req_{}_{}", self.generation, self.next_request);
        self.next_request += 1;
        self.registry.register(&request_id, deadline_ms);
        let frame = RequestEnvelope::new(&request_id, method, params_json, deadline_ms).to_json() + "\n";
        self.write_raw_frame(&frame, deadline_ms)
    }

    pub fn write_raw_frame(&mut self, frame: &str, deadline_ms: u64) -> Result<ResponseEnvelope, String> {
        if self.child.try_wait().map_err(|error| error.to_string())?.is_some() {
            self.degraded = true;
            self.registry.mark_restarted();
            return Ok(ResponseEnvelope::synthetic_error("sidecar.restarted"));
        }
        let response = self.invoke_one_shot(frame, deadline_ms)?;
        if let Some(request_id) = response.request_id.as_deref() {
            self.registry.accept_response(self.generation, request_id);
        }
        Ok(response)
    }

    pub fn health_ping(&mut self, deadline_ms: u64) -> Result<ResponseEnvelope, String> {
        let response = self.request("sidecar.health", "{}", deadline_ms)?;
        if !response.ok {
            self.degraded = true;
            return Err("health ping failed".to_string());
        }
        Ok(response)
    }

    pub fn kill_child_for_test(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }

    fn invoke_one_shot(&mut self, frame: &str, _deadline_ms: u64) -> Result<ResponseEnvelope, String> {
        let runtime_paths = RuntimePaths::for_dev_repo(self.repo_root.clone())?;
        let mut child = Command::new(python_executable())
            .arg("-u")
            .arg("-m")
            .arg("python_core.sidecar_main")
            .arg("--stdio")
            .arg("--runtime-paths-json")
            .arg(runtime_paths.to_json())
            .current_dir(&self.repo_root)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|error| format!("spawn sidecar request failed: {error}"))?;
        if let Some(mut stdin) = child.stdin.take() {
            stdin.write_all(frame.as_bytes()).map_err(|error| error.to_string())?;
            stdin.flush().map_err(|error| error.to_string())?;
        }
        let output = child.wait_with_output().map_err(|error| error.to_string())?;
        if !output.status.success() {
            self.degraded = true;
            self.registry.mark_restarted();
            return Ok(ResponseEnvelope::synthetic_error("sidecar.restarted"));
        }
        let stdout = String::from_utf8_lossy(&output.stdout);
        let response_line = stdout.lines().last().ok_or_else(|| "empty sidecar stdout".to_string())?;
        ResponseEnvelope::from_json(response_line)
    }
}

fn python_executable() -> String {
    if let Ok(value) = std::env::var("PYTHON") {
        return value;
    }
    if let Ok(prefix) = std::env::var("CONDA_PREFIX") {
        let candidate = std::path::Path::new(&prefix).join(if cfg!(windows) { "python.exe" } else { "bin/python" });
        if candidate.exists() {
            return candidate.to_string_lossy().to_string();
        }
    }
    "python".to_string()
}

impl Drop for SidecarSupervisor {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

impl RequestRegistry {
    pub fn new(generation: u64) -> Self {
        Self {
            generation,
            pending: HashMap::new(),
        }
    }

    pub fn generation(&self) -> u64 {
        self.generation
    }

    pub fn register(&mut self, request_id: &str, deadline_ms: u64) {
        self.pending.insert(
            request_id.to_string(),
            Instant::now() + Duration::from_millis(deadline_ms),
        );
    }

    pub fn pending_request_ids(&self) -> Vec<String> {
        self.pending.keys().cloned().collect()
    }

    pub fn expire_deadlines(&mut self) {
        let now = Instant::now();
        self.pending.retain(|_, deadline| *deadline > now);
    }

    pub fn accept_response(&mut self, generation: u64, request_id: &str) -> bool {
        if generation != self.generation {
            return false;
        }
        self.pending.remove(request_id).is_some()
    }

    pub fn mark_restarted(&mut self) -> Vec<RestartedRequest> {
        if self.pending.is_empty() {
            return Vec::new();
        }
        let restarted = self
            .pending
            .keys()
            .cloned()
            .map(|request_id| RestartedRequest {
                request_id,
                error_code: "sidecar.restarted".to_string(),
            })
            .collect();
        self.pending.clear();
        self.generation += 1;
        restarted
    }
}
