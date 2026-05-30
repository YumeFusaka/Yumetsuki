use std::path::PathBuf;

use yumetsuki_desktop::sidecar::{RequestRegistry, SidecarSupervisor};

fn repo_root() -> PathBuf {
    let mut path = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    loop {
        if path.join("python_core").join("sidecar_main.py").exists() {
            return path;
        }
        assert!(path.pop(), "failed to locate repo root from CARGO_MANIFEST_DIR");
    }
}

#[test]
fn restart_increments_generation_and_marks_pending_once() {
    let mut registry = RequestRegistry::new(1);
    registry.register("req_chat", 30_000);
    registry.register("req_tts", 30_000);

    let first = registry.mark_restarted();
    let second = registry.mark_restarted();

    assert_eq!(first.len(), 2);
    assert!(second.is_empty());
    assert!(first.iter().all(|item| item.error_code == "sidecar.restarted"));
    assert_eq!(registry.generation(), 2);
}

#[test]
fn health_ping_failure_marks_supervisor_degraded() {
    let root = repo_root();
    let mut supervisor = SidecarSupervisor::spawn_dev(root).unwrap();
    supervisor.kill_child_for_test();

    assert!(supervisor.health_ping(500).is_err());
    assert!(supervisor.is_degraded());
}

#[test]
fn write_after_child_exit_fails_pending_request() {
    let root = repo_root();
    let mut supervisor = SidecarSupervisor::spawn_dev(root).unwrap();
    supervisor.kill_child_for_test();

    let response = supervisor
        .request("sidecar.hello", "{\"supported_versions\":[1]}", 500)
        .unwrap();
    assert!(!response.ok);
    assert_eq!(response.error_code(), Some("sidecar.restarted".to_string()));
}
