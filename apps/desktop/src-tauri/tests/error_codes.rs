use std::collections::HashSet;

use yumetsuki_desktop::error_codes::RPC_ERROR_CODES;

#[test]
fn error_codes_include_phase1_contract_codes() {
    assert!(RPC_ERROR_CODES.contains(&"rpc.protocol_unsupported"));
    assert!(RPC_ERROR_CODES.contains(&"rpc.method_not_found"));
    assert!(RPC_ERROR_CODES.contains(&"sidecar.not_ready"));
    assert!(RPC_ERROR_CODES.contains(&"filesystem.path_out_of_scope"));
}

#[test]
fn error_codes_are_unique() {
    let unique: HashSet<&str> = RPC_ERROR_CODES.iter().copied().collect();
    assert_eq!(unique.len(), RPC_ERROR_CODES.len());
}
