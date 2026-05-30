use std::path::{Component, Path, PathBuf};

pub fn assert_path_in_scope(path: PathBuf, allowed_roots: &[PathBuf]) -> Result<PathBuf, String> {
    if contains_parent_component(&path) {
        return Err("filesystem.path_out_of_scope".to_string());
    }
    if is_unc_path(&path) {
        return Err("filesystem.path_out_of_scope".to_string());
    }
    let resolved = resolve_path(&path);
    for root in allowed_roots {
        let resolved_root = resolve_path(root);
        if resolved.starts_with(&resolved_root) {
            return Ok(resolved);
        }
    }
    Err("filesystem.path_out_of_scope".to_string())
}

pub fn is_safe_file_name(name: &str) -> bool {
    if name.is_empty() || name == "." || name == ".." {
        return false;
    }
    name.chars()
        .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '_' | '-' | '.'))
}

fn resolve_path(path: &Path) -> PathBuf {
    path.canonicalize().unwrap_or_else(|_| normalize_lexically(path))
}

fn normalize_lexically(path: &Path) -> PathBuf {
    let mut output = PathBuf::new();
    for component in path.components() {
        match component {
            Component::CurDir => {}
            Component::ParentDir => {
                output.pop();
            }
            other => output.push(other.as_os_str()),
        }
    }
    output
}

fn contains_parent_component(path: &Path) -> bool {
    path.components().any(|component| matches!(component, Component::ParentDir))
}

fn is_unc_path(path: &Path) -> bool {
    path.to_string_lossy().replace('/', "\\").starts_with("\\\\")
}
