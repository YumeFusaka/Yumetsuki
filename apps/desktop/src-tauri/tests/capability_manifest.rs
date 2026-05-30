use std::collections::HashSet;
use std::fs;
use std::path::PathBuf;

fn repo_root() -> PathBuf {
    let mut path = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    loop {
        if path.join("python_core").join("sidecar_main.py").exists() {
            return path;
        }
        assert!(path.pop(), "failed to locate repo root");
    }
}

fn read_capability(name: &str) -> String {
    fs::read_to_string(repo_root().join("apps/desktop/src-tauri/capabilities").join(name))
        .expect("capability file missing")
}

#[test]
fn capability_manifests_exist() {
    for name in ["main.json", "pet.json", "settings.json", "diagnostics.json"] {
        assert!(read_capability(name).contains("\"identifier\""));
    }
}

#[test]
fn pet_window_does_not_grant_settings_or_diagnostics() {
    let pet = read_capability("pet.json");
    assert!(!pet.contains("settings"));
    assert!(!pet.contains("diagnostics"));
}

#[test]
fn forbidden_permissions_are_not_granted() {
    let files = ["main.json", "pet.json", "settings.json", "diagnostics.json"];
    for name in files {
        let content = read_capability(name);
        assert!(!content.contains("\"shell\""));
        assert!(!content.contains("\"clipboard\""));
        assert!(!content.contains("\"opener\""));
        assert!(!content.contains("\"http\""));
        assert!(!content.contains("\"file\""));
    }
}

#[test]
fn all_capabilities_cover_expected_windows() {
    let mut windows = HashSet::new();
    for name in ["main.json", "pet.json", "settings.json", "diagnostics.json"] {
        let content = read_capability(name);
        for window in ["main", "pet", "settings", "diagnostics"] {
            if content.contains(&format!("\"{window}\"")) {
                windows.insert(window);
            }
        }
    }
    assert_eq!(windows.len(), 4);
}
