use std::sync::{Arc, Mutex};

use serde_json::json;
use yumetsuki_desktop::rpc::RpcContext;
use yumetsuki_desktop::runtime_paths::{RuntimeMode, RuntimePaths};
use yumetsuki_desktop::sidecar::SidecarSupervisor;

fn test_paths(label: &str) -> RuntimePaths {
    let root = std::env::temp_dir()
        .join("yumetsuki-supervisor-test")
        .join(format!("{}-{label}", std::process::id()));
    RuntimePaths::from_app_data(root, "resources", RuntimeMode::Dev)
        .expect("测试运行期路径应有效")
}

#[test]
fn hello_starts_real_python_sidecar_and_reports_generation() {
    let mut supervisor = SidecarSupervisor::new();
    let paths = test_paths("hello");
    let context = RpcContext::new("req_hello".into(), "trace_hello".into(), None);
    let response = supervisor
        .hello(context, &paths)
        .expect("hello 应成功");

    assert!(!response.accepted);
    assert_eq!(response.request_id, "req_hello");
    assert_eq!(response.result.selected_protocol_version, 1);
    assert_eq!(response.result.min_compatible_protocol_version, 1);
    assert!(response.result.runtime_paths_ready);
    assert_eq!(response.result.sidecar_generation, 1);
    assert!(!response.result.sidecar_version.trim().is_empty());
    assert!(response
        .result
        .capabilities
        .contains(&"chat.send".to_string()));
}

#[test]
fn chat_send_routes_through_python_sidecar_and_emits_accepted_task() {
    let mut supervisor = SidecarSupervisor::new();
    let paths = test_paths("chat-send");
    let events: Arc<Mutex<Vec<String>>> = Arc::new(Mutex::new(Vec::new()));
    let bridge_events = Arc::clone(&events);
    supervisor.set_event_bridge(Arc::new(move |event| {
        if let Ok(mut collected) = bridge_events.lock() {
            collected.push(event.event_type);
        }
    }));
    supervisor
        .hello(
            RpcContext::new("req_boot".into(), "trace_boot".into(), None),
            &paths,
        )
        .expect("hello 应成功");

    let context = RpcContext::new(
        "req_chat".into(),
        "trace_chat".into(),
        Some("session_1".into()),
    );
    let response = supervisor
        .dispatch_json_command(
            "chat.send",
            context,
            json!({ "text": "hello", "session_id": "session_1" }),
            true,
        )
        .expect("chat.send 应被接受");

    assert!(response.accepted);
    assert_eq!(response.request_id, "req_chat");
    assert_eq!(response.trace_id, "trace_chat");
    assert_eq!(response.result["status"], "accepted");
    assert_eq!(response.result["task_type"], "chat.send");
    let started_at = std::time::Instant::now();
    while started_at.elapsed() < std::time::Duration::from_secs(2) {
        if events
            .lock()
            .expect("事件应可读取")
            .contains(&"chat.done".to_string())
        {
            break;
        }
        std::thread::sleep(std::time::Duration::from_millis(10));
    }
    let collected = events.lock().expect("事件应可读取");
    assert!(collected.contains(&"chat.started".to_string()));
    assert!(collected.contains(&"chat.delta".to_string()));
    assert!(collected.contains(&"chat.done".to_string()));
}

#[test]
fn cancel_known_request_is_projected_into_python_terminal_state() {
    let mut supervisor = SidecarSupervisor::new();
    let paths = test_paths("cancel");
    supervisor
        .hello(
            RpcContext::new("req_boot".into(), "trace_boot".into(), None),
            &paths,
        )
        .expect("hello 应成功");

    supervisor
        .dispatch_json_command(
            "chat.send",
            RpcContext::new("req_target".into(), "trace_chat".into(), None),
            json!({ "text": "hello", "session_id": "sess_cancel" }),
            true,
        )
        .expect("chat.send 应被接受");

    let cancel = supervisor
        .cancel(
            RpcContext::new("req_cancel".into(), "trace_cancel".into(), None),
            "req_target".into(),
        )
        .expect("cancel 应成功");

    assert!(cancel.accepted);
    assert_eq!(cancel.result.target_request_id, "req_target");
    assert!(matches!(
        cancel.result.status.as_str(),
        "cancelled" | "already_terminal"
    ));
    assert!(matches!(
        cancel.result.terminal_state.as_str(),
        "cancelled" | "already_terminal" | "done"
    ));
}

#[test]
fn shutdown_blocks_business_requests_until_next_hello_restart() {
    let mut supervisor = SidecarSupervisor::new();
    let paths = test_paths("shutdown");
    supervisor
        .hello(
            RpcContext::new("req_boot".into(), "trace_boot".into(), None),
            &paths,
        )
        .expect("hello 应成功");
    let generation = supervisor.generation();

    let shutdown = supervisor
        .shutdown(RpcContext::new("req_shutdown".into(), "trace_shutdown".into(), None))
        .expect("shutdown 应被接受");

    assert!(shutdown.accepted);
    assert_eq!(shutdown.result.sidecar_generation, generation);

    let config = supervisor.config_get_all(
        RpcContext::new("req_config".into(), "trace_config".into(), None),
        None,
    );
    assert!(config.is_err());

    let restart = supervisor
        .hello(
            RpcContext::new("req_restart".into(), "trace_restart".into(), None),
            &paths,
        )
        .expect("hello 应重启 sidecar");
    assert!(restart.result.sidecar_generation > generation);
}

#[test]
fn phase4_bridge_methods_route_tools_plugins_mcp_and_long_tasks() {
    let mut supervisor = SidecarSupervisor::new();
    let paths = test_paths("phase4-bridge");
    supervisor
        .hello(
            RpcContext::new("req_phase4_boot".into(), "trace_phase4_boot".into(), None),
            &paths,
        )
        .expect("hello 应成功");

    let tools = supervisor
        .dispatch_json_command(
            "tools.list",
            RpcContext::new("req_tools_list".into(), "trace_phase4".into(), None),
            json!({ "include_disabled": false }),
            false,
        )
        .expect("tools.list 应成功");
    assert!(!tools.accepted);
    assert_eq!(tools.result["items"][0]["tool_name"], "example_echo__echo");

    let plugins = supervisor
        .dispatch_json_command(
            "plugins.status",
            RpcContext::new("req_plugins_status".into(), "trace_phase4".into(), None),
            json!({ "plugin_id": "example-plugin" }),
            false,
        )
        .expect("plugins.status 应成功");
    assert!(!plugins.accepted);
    assert_eq!(plugins.result["status"]["plugin_id"], "example-plugin");

    let mcp = supervisor
        .dispatch_json_command(
            "mcp.list_servers",
            RpcContext::new("req_mcp_list_servers".into(), "trace_phase4".into(), None),
            json!({ "include_disabled": false }),
            false,
        )
        .expect("mcp.list_servers 应成功");
    assert!(!mcp.accepted);
    assert_eq!(mcp.result["servers"], json!([]));

    let refresh = supervisor
        .dispatch_json_command(
            "plugins.refresh",
            RpcContext::new("req_plugins_refresh".into(), "trace_phase4".into(), None),
            json!({ "filters": {} }),
            true,
        )
        .expect("plugins.refresh 应成功");
    assert!(refresh.accepted);
    assert_eq!(refresh.result["task_type"], "plugins.refresh");
}
