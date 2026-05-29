use std::fs;

use yumetsuki_desktop::path_scope::{validate_safe_filename, PathScope};
use yumetsuki_desktop::runtime_paths::{assert_in_scope, RuntimeMode, RuntimePathError, RuntimePaths};

#[test]
fn runtime_paths_are_derived_from_app_data() {
    let root = std::env::temp_dir().join("yumetsuki-runtime-paths-test");
    let resources = root.join("resources");
    let paths =
        RuntimePaths::from_app_data_with_repo_root(&root, &resources, RuntimeMode::Dev, None)
            .expect("开发模式运行期路径应有效");

    assert_eq!(paths.config_dir, paths.app_data_dir.join("config"));
    assert_eq!(paths.log_dir, paths.app_data_dir.join("logs"));
    assert_eq!(paths.memory_dir, paths.app_data_dir.join("memory"));
    assert_eq!(paths.vision_dir, paths.app_data_dir.join("vision"));
    assert_eq!(
        paths.browser_sessions_dir,
        paths.app_data_dir.join("browser_sessions")
    );
    assert_eq!(paths.temp_dir, paths.app_data_dir.join("temp"));
    assert_eq!(paths.models_dir, paths.app_data_dir.join("models"));

    let json = paths.to_injected_json();
    assert!(json.get("app_data_dir").is_some());
    assert!(json.get("resource_dir").is_some());
    assert!(json.get("platform").is_some());
}

#[test]
fn release_mode_rejects_repo_data_runtime_root() {
    let repo_root = std::env::temp_dir().join("yumetsuki-repo-root-test");
    let app_data = repo_root.join("data");
    let resources = repo_root.join("resources");
    let err = RuntimePaths::from_app_data_with_repo_root(
        &app_data,
        &resources,
        RuntimeMode::Release,
        Some(&repo_root),
    )
    .expect_err("发布模式必须拒绝仓库内 data 根目录");

    assert!(matches!(err, RuntimePathError::RepoDataInRelease(_)));
}

#[test]
fn scope_check_allows_children_and_rejects_siblings() {
    let root = std::env::temp_dir().join("yumetsuki-scope-test");
    let allowed = root.join("allowed");
    let sibling = root.join("sibling");
    fs::create_dir_all(&allowed).expect("创建允许根目录");
    fs::create_dir_all(&sibling).expect("创建同级目录");

    let child = allowed.join("logs").join("app.jsonl");
    let resolved = assert_in_scope(&child, &[allowed.as_path()]).expect("子路径应被允许");
    assert!(resolved.starts_with(allowed.canonicalize().expect("允许根目录应可规范化")));

    let rejected = assert_in_scope(&sibling.join("app.jsonl"), &[allowed.as_path()]);
    assert!(rejected.is_err());
}

#[test]
fn filename_scope_rejects_traversal_and_windows_prefixes() {
    assert!(validate_safe_filename("system_config.yaml").is_ok());
    assert!(validate_safe_filename("agent-v1.json").is_ok());
    assert!(validate_safe_filename("../api.yaml").is_err());
    assert!(validate_safe_filename("C:\\secret.txt").is_err());
    assert!(validate_safe_filename("\\\\server\\share").is_err());
    assert!(validate_safe_filename("with space.txt").is_err());
}

#[test]
fn path_scope_resolves_safe_child_under_allowed_root() {
    let root = std::env::temp_dir().join("yumetsuki-path-scope-test");
    fs::create_dir_all(&root).expect("创建根目录");
    let scope = PathScope::new([root.clone()]);
    let child = scope
        .resolve_child(&root, "platform.jsonl")
        .expect("安全子路径应在 scope 内");
    assert!(child.starts_with(root.canonicalize().expect("根目录应可规范化")));
}
