use yumetsuki_desktop::rpc_schema::{RPC_EVENTS, RPC_METHODS, SCHEMA_HASH};

#[test]
fn schema_hash_is_pinned() {
    assert_eq!(SCHEMA_HASH.len(), 64);
}

#[test]
fn security_confirm_required_is_event_only() {
    assert!(!RPC_METHODS.contains(&"security.confirm_required"));
    assert!(RPC_EVENTS.contains(&"security.confirm_required"));
}

#[test]
fn sidecar_cancel_is_only_cancel_method() {
    let cancel_methods: Vec<&str> = RPC_METHODS
        .iter()
        .copied()
        .filter(|method| method.contains("cancel"))
        .collect();
    assert_eq!(cancel_methods, vec!["sidecar.cancel"]);
}
