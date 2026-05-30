use std::path::{Path, PathBuf};

use crate::rpc::escape_json;

#[derive(Debug, Clone)]
pub struct RuntimePaths {
    pub mode: String,
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
    pub repo_root: PathBuf,
}

impl RuntimePaths {
    pub fn for_dev_repo(repo_root: PathBuf) -> Result<Self, String> {
        let root = resolve_lossy(&repo_root);
        let app_data = root.join("data");
        Ok(Self {
            mode: "dev".to_string(),
            app_data_dir: app_data.clone(),
            config_dir: app_data.join("config"),
            log_dir: app_data.join("logs"),
            memory_dir: app_data.join("memory"),
            vision_dir: app_data.join("vision"),
            browser_sessions_dir: app_data.join("browser_sessions"),
            temp_dir: app_data.join("temp"),
            resource_dir: root.join("resources"),
            models_dir: app_data.join("models"),
            platform: std::env::consts::OS.to_string(),
            repo_root: root,
        })
    }

    pub fn to_json(&self) -> String {
        format!(
            "{{\"mode\":\"{}\",\"app_data_dir\":\"{}\",\"config_dir\":\"{}\",\"log_dir\":\"{}\",\"memory_dir\":\"{}\",\"vision_dir\":\"{}\",\"browser_sessions_dir\":\"{}\",\"temp_dir\":\"{}\",\"resource_dir\":\"{}\",\"models_dir\":\"{}\",\"platform\":\"{}\",\"repo_root\":\"{}\"}}",
            escape_json(&self.mode),
            path_json(&self.app_data_dir),
            path_json(&self.config_dir),
            path_json(&self.log_dir),
            path_json(&self.memory_dir),
            path_json(&self.vision_dir),
            path_json(&self.browser_sessions_dir),
            path_json(&self.temp_dir),
            path_json(&self.resource_dir),
            path_json(&self.models_dir),
            escape_json(&self.platform),
            path_json(&self.repo_root)
        )
    }
}

fn resolve_lossy(path: &Path) -> PathBuf {
    normalize_windows_extended_path(path.canonicalize().unwrap_or_else(|_| path.to_path_buf()))
}

fn path_json(path: &Path) -> String {
    escape_json(&path.to_string_lossy())
}

fn normalize_windows_extended_path(path: PathBuf) -> PathBuf {
    let raw = path.to_string_lossy();
    if let Some(stripped) = raw.strip_prefix(r"\\?\") {
        return PathBuf::from(stripped);
    }
    path
}
