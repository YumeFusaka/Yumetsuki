use std::env;
use std::path::{Component, Path, PathBuf};

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RuntimeMode {
    Dev,
    Release,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RuntimePaths {
    pub app_data_dir: PathBuf,
    pub config_dir: PathBuf,
    pub log_dir: PathBuf,
    pub memory_dir: PathBuf,
    pub vision_dir: PathBuf,
    pub browser_sessions_dir: PathBuf,
    pub temp_dir: PathBuf,
    pub resource_dir: PathBuf,
    pub models_dir: PathBuf,
    pub platform: String,
}

#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum RuntimePathError {
    #[error("路径不能为空")]
    EmptyPath,
    #[error("发布模式运行期路径不能指向仓库 data 目录: {0}")]
    RepoDataInRelease(String),
    #[error("路径不在允许范围内: {0}")]
    OutOfScope(String),
}

impl RuntimePaths {
    pub fn for_current_process(mode: RuntimeMode) -> Self {
        let app_data = default_app_data_dir();
        let resource_dir = env::current_dir()
            .unwrap_or_else(|_| PathBuf::from("."))
            .join("resources");
        Self::from_app_data(app_data, resource_dir, mode).unwrap_or_else(|_| {
            let fallback = env::temp_dir().join("yumetsuki");
            Self::from_app_data(fallback, PathBuf::from("resources"), RuntimeMode::Dev)
                .expect("开发模式兜底运行期路径必须有效")
        })
    }

    pub fn from_app_data(
        app_data_dir: impl AsRef<Path>,
        resource_dir: impl AsRef<Path>,
        mode: RuntimeMode,
    ) -> Result<Self, RuntimePathError> {
        let repo_root = env::current_dir().ok();
        Self::from_app_data_with_repo_root(app_data_dir, resource_dir, mode, repo_root.as_deref())
    }

    pub fn from_app_data_with_repo_root(
        app_data_dir: impl AsRef<Path>,
        resource_dir: impl AsRef<Path>,
        mode: RuntimeMode,
        repo_root: Option<&Path>,
    ) -> Result<Self, RuntimePathError> {
        let app_data_dir = resolve_path(app_data_dir.as_ref())?;
        let resource_dir = resolve_path(resource_dir.as_ref())?;

        if mode == RuntimeMode::Release {
            reject_repo_data(&app_data_dir, repo_root)?;
        }

        Ok(Self {
            config_dir: app_data_dir.join("config"),
            log_dir: app_data_dir.join("logs"),
            memory_dir: app_data_dir.join("memory"),
            vision_dir: app_data_dir.join("vision"),
            browser_sessions_dir: app_data_dir.join("browser_sessions"),
            temp_dir: app_data_dir.join("temp"),
            models_dir: app_data_dir.join("models"),
            app_data_dir,
            resource_dir,
            platform: current_platform().to_string(),
        })
    }

    pub fn assert_in_app_data_scope(&self, path: impl AsRef<Path>) -> Result<PathBuf, RuntimePathError> {
        assert_in_scope(path.as_ref(), &[self.app_data_dir.as_path()])
    }

    pub fn app_data_roots(&self) -> [&Path; 1] {
        [self.app_data_dir.as_path()]
    }

    pub fn to_injected_json(&self) -> serde_json::Value {
        serde_json::json!({
            "app_data_dir": self.app_data_dir,
            "config_dir": self.config_dir,
            "log_dir": self.log_dir,
            "memory_dir": self.memory_dir,
            "vision_dir": self.vision_dir,
            "browser_sessions_dir": self.browser_sessions_dir,
            "temp_dir": self.temp_dir,
            "resource_dir": self.resource_dir,
            "models_dir": self.models_dir,
            "platform": self.platform,
        })
    }
}

pub fn assert_in_scope(path: &Path, allowed_roots: &[&Path]) -> Result<PathBuf, RuntimePathError> {
    let resolved = resolve_path(path)?;
    for root in allowed_roots {
        let root = resolve_path(root)?;
        if resolved == root || resolved.starts_with(&root) {
            return Ok(resolved);
        }
    }
    Err(RuntimePathError::OutOfScope(resolved.display().to_string()))
}

pub fn resolve_path(path: &Path) -> Result<PathBuf, RuntimePathError> {
    if path.as_os_str().is_empty() {
        return Err(RuntimePathError::EmptyPath);
    }
    if let Ok(canonical) = path.canonicalize() {
        return Ok(canonical);
    }

    let absolute = if path.is_absolute() {
        path.to_path_buf()
    } else {
        env::current_dir()
            .unwrap_or_else(|_| PathBuf::from("."))
            .join(path)
    };
    Ok(resolve_existing_ancestor(&absolute))
}

fn resolve_existing_ancestor(path: &Path) -> PathBuf {
    let normalized = normalize_lexically(path);
    let mut ancestor = normalized.as_path();
    let mut missing_parts = Vec::new();

    while !ancestor.as_os_str().is_empty() {
        if let Ok(canonical) = ancestor.canonicalize() {
            let mut resolved = canonical;
            for part in missing_parts.iter().rev() {
                resolved.push(part);
            }
            return normalize_lexically(&resolved);
        }

        if let Some(file_name) = ancestor.file_name() {
            missing_parts.push(file_name.to_os_string());
        }

        match ancestor.parent() {
            Some(parent) if parent != ancestor => ancestor = parent,
            _ => break,
        }
    }

    normalized
}

fn normalize_lexically(path: &Path) -> PathBuf {
    let mut normalized = PathBuf::new();
    for component in path.components() {
        match component {
            Component::CurDir => {}
            Component::ParentDir => {
                normalized.pop();
            }
            Component::Prefix(prefix) => normalized.push(prefix.as_os_str()),
            Component::RootDir => normalized.push(component.as_os_str()),
            Component::Normal(part) => normalized.push(part),
        }
    }
    normalized
}

fn reject_repo_data(path: &Path, repo_root: Option<&Path>) -> Result<(), RuntimePathError> {
    if let Some(repo_root) = repo_root {
        let repo_root = resolve_path(repo_root)?;
        let repo_data = repo_root.join("data");
        if path == repo_data || path.starts_with(repo_data) {
            return Err(RuntimePathError::RepoDataInRelease(path.display().to_string()));
        }
    }
    Ok(())
}

fn default_app_data_dir() -> PathBuf {
    if cfg!(target_os = "windows") {
        if let Some(app_data) = env::var_os("APPDATA") {
            return PathBuf::from(app_data).join("Yumetsuki");
        }
    }
    if let Some(home) = env::var_os("HOME") {
        return PathBuf::from(home).join(".yumetsuki");
    }
    env::temp_dir().join("yumetsuki")
}

fn current_platform() -> &'static str {
    if cfg!(target_os = "windows") {
        "windows"
    } else if cfg!(target_os = "macos") {
        "macos"
    } else {
        "linux"
    }
}
