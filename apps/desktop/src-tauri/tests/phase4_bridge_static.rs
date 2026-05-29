use yumetsuki_desktop::capability_manifest::{registered_commands, security_classes};

#[test]
fn phase4_bridge_commands_are_registered_and_classified() {
    let expected = [
        "tools_list",
        "tools_call",
        "tools_audit_query",
        "plugins_status",
        "plugins_refresh",
        "plugins_enable",
        "plugins_disable",
        "mcp_list_servers",
        "mcp_refresh",
        "mcp_call_tool",
        "security_list_grants",
    ];
    let registered = registered_commands();
    let classes = security_classes();

    for command in expected {
        assert!(registered.contains(command), "{command} 必须注册到 command catalog");
        assert!(classes.contains_key(command), "{command} 必须有安全分类");
    }
}

#[test]
fn phase4_bridge_does_not_inject_placeholder_required_params_or_tokens() {
    let source = include_str!("../src/lib.rs");

    assert!(source.contains("required_string(params.tool_name, \"tool_name\")?"));
    assert!(source.contains("required_string(params.source, \"source\")?"));
    assert!(source.contains("required_object(params.arguments, \"arguments\")?"));
    assert!(source.contains("required_string(params.confirm_token, \"confirm_token\")?"));
    assert!(!source.contains("safe_string(params.plugin_id"));
    assert!(!source.contains("safe_string(params.server_id"));
    assert!(!source.contains("unwrap_or_else(|| \"<redacted>\".to_string())"));
}
