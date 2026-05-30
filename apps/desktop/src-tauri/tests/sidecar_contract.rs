use std::path::PathBuf;

use yumetsuki_desktop::rpc::{RequestEnvelope, ResponseEnvelope};
use yumetsuki_desktop::runtime_paths::RuntimePaths;
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
fn runtime_paths_can_build_dev_payload() {
    let root = repo_root();
    let paths = RuntimePaths::for_dev_repo(root.clone()).unwrap();
    let json = paths.to_json();
    assert!(json.contains("\"mode\":\"dev\""));
    assert!(json.contains("\"config_dir\""));
    assert!(paths.config_dir.starts_with(&paths.app_data_dir));
}

#[test]
fn request_envelope_uses_request_id_not_legacy_id() {
    let request = RequestEnvelope::new("req_1", "sidecar.hello", "{\"supported_versions\":[1]}", 1000);
    let json = request.to_json();
    assert!(json.contains("\"request_id\":\"req_1\""));
    assert!(!json.contains("\"id\""));
}

#[test]
fn supervisor_can_send_hello_to_python_sidecar() {
    let root = repo_root();
    let mut supervisor = SidecarSupervisor::spawn_dev(root).unwrap();
    let response = supervisor
        .request("sidecar.hello", "{\"supported_versions\":[1]}", 3000)
        .unwrap();

    assert!(response.ok);
    assert_eq!(response.result_string("schema_hash").unwrap().len(), 64);
    assert_eq!(response.result_i64("selected_protocol_version"), Some(1));
    assert_eq!(supervisor.generation(), 1);
}

#[test]
fn invalid_frame_returns_protocol_error() {
    let root = repo_root();
    let mut supervisor = SidecarSupervisor::spawn_dev(root).unwrap();
    let response = supervisor.write_raw_frame("not-json\n", 3000).unwrap();

    assert!(!response.ok);
    assert_eq!(response.error_code(), Some("rpc.invalid_frame".to_string()));
}

#[test]
fn response_parser_extracts_error_code() {
    let response = ResponseEnvelope::from_json(
        r#"{"kind":"response","ok":false,"request_id":"r","error":{"code":"sidecar.restarted"},"result":null}"#,
    )
    .unwrap();
    assert_eq!(response.error_code(), Some("sidecar.restarted".to_string()));
}

#[test]
fn request_registry_releases_waiter_on_deadline_and_rejects_late_response() {
    let mut registry = RequestRegistry::new(7);
    registry.register("req_deadline", 0);
    registry.expire_deadlines();

    assert!(registry.pending_request_ids().is_empty());
    assert!(!registry.accept_response(7, "req_deadline"));
}
