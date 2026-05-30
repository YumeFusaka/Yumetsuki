use std::path::PathBuf;

use yumetsuki_desktop::path_scope::{assert_path_in_scope, is_safe_file_name};
use yumetsuki_desktop::url_safety::{needs_confirmation, normalize_url};

fn repo_root() -> PathBuf {
    let mut path = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    loop {
        if path.join("python_core").join("sidecar_main.py").exists() {
            return path;
        }
        assert!(path.pop(), "failed to locate repo root");
    }
}

#[test]
fn rejects_parent_and_drive_escape() {
    let root = repo_root();
    let scope = root.join("data");
    assert!(assert_path_in_scope(scope.join("config"), &[scope.clone()]).is_ok());
    assert!(assert_path_in_scope(root.join("..").join("escape"), &[scope]).is_err());
}

#[test]
fn rejects_unc_and_symlink_escape() {
    assert!(normalize_url("file:///c:/users/test").is_err());
}

#[test]
fn file_names_are_restricted() {
    assert!(is_safe_file_name("ok_name-1.txt"));
    assert!(!is_safe_file_name("../escape"));
    assert!(!is_safe_file_name("C:\\escape.txt"));
}

#[test]
fn localhost_and_private_network_need_confirmation() {
    assert!(needs_confirmation("http://127.0.0.1:3000").is_ok());
    assert!(needs_confirmation("http://10.0.0.1").is_ok());
    assert!(needs_confirmation("https://example.com").is_ok());
}
