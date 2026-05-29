use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};

use serde::Deserialize;
use yumetsuki_desktop::capability_manifest::{
    commands_missing_security_class, dangerous_permission_prefixes, registered_commands,
};

#[derive(Debug, Deserialize)]
struct Capability {
    identifier: String,
    windows: Vec<String>,
    permissions: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct PermissionFile {
    permission: Vec<Permission>,
}

#[derive(Debug, Deserialize)]
struct Permission {
    identifier: String,
    commands: Commands,
}

#[derive(Debug, Deserialize)]
struct Commands {
    #[serde(default)]
    allow: Vec<String>,
    #[serde(default)]
    deny: Vec<String>,
}

fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn read_capabilities() -> Vec<Capability> {
    let mut capabilities = Vec::new();
    for entry in fs::read_dir(root().join("capabilities")).expect("capabilities 目录存在") {
        let entry = entry.expect("capability 文件项");
        if entry.path().extension().and_then(|ext| ext.to_str()) == Some("json") {
            let text = fs::read_to_string(entry.path()).expect("读取 capability JSON");
            capabilities.push(serde_json::from_str(&text).expect("解析 capability JSON"));
        }
    }
    capabilities
}

fn read_permissions() -> BTreeMap<String, Vec<String>> {
    let mut permissions = BTreeMap::new();
    for entry in fs::read_dir(root().join("permissions")).expect("permissions 目录存在") {
        let entry = entry.expect("permission 文件项");
        if entry.path().extension().and_then(|ext| ext.to_str()) == Some("toml") {
            let text = fs::read_to_string(entry.path()).expect("读取 permission TOML");
            let parsed: PermissionFile = toml::from_str(&text).expect("解析 permission TOML");
            for permission in parsed.permission {
                assert!(
                    permission.commands.deny.is_empty(),
                    "低权限 capability 中 deny 列表应保持为空"
                );
                permissions.insert(permission.identifier, permission.commands.allow);
            }
        }
    }
    permissions
}

fn commands_for_capability(capability: &Capability, permissions: &BTreeMap<String, Vec<String>>) -> BTreeSet<String> {
    let mut commands = BTreeSet::new();
    for permission in &capability.permissions {
        if let Some(allowed) = permissions.get(permission) {
            commands.extend(allowed.iter().cloned());
        }
    }
    commands
}

#[test]
fn registered_commands_have_security_classes() {
    assert!(
        commands_missing_security_class().is_empty(),
        "每个 command 都必须有安全分类"
    );
}

#[test]
fn every_registered_command_is_allowed_by_at_least_one_capability() {
    let capabilities = read_capabilities();
    let permissions = read_permissions();
    let mut allowed = BTreeSet::new();
    for capability in &capabilities {
        allowed.extend(commands_for_capability(capability, &permissions));
    }

    let registered = registered_commands()
        .into_iter()
        .map(str::to_string)
        .collect::<BTreeSet<_>>();

    assert_eq!(allowed, registered);
}

#[test]
fn capability_commands_are_registered() {
    let capabilities = read_capabilities();
    let permissions = read_permissions();
    let registered = registered_commands()
        .into_iter()
        .map(str::to_string)
        .collect::<BTreeSet<_>>();

    for capability in &capabilities {
        for command in commands_for_capability(capability, &permissions) {
            assert!(
                registered.contains(&command),
                "{} 引用了未注册 command {}",
                capability.identifier,
                command
            );
        }
    }
}

#[test]
fn pet_capability_is_low_privilege() {
    let capabilities = read_capabilities();
    let permissions = read_permissions();
    let pet = capabilities
        .iter()
        .find(|capability| capability.identifier == "pet")
        .expect("pet capability 存在");

    assert_eq!(pet.windows, vec!["pet"]);
    let commands = commands_for_capability(pet, &permissions);
    assert_eq!(
        commands,
        ["chat_send".to_string(), "sidecar_cancel".to_string()]
            .into_iter()
            .collect::<BTreeSet<_>>()
    );
    assert!(!pet.permissions.iter().any(|permission| {
        permission.contains("config") || permission.contains("logs") || permission.contains("diagnostics")
    }));
}

#[test]
fn dangerous_plugin_permissions_are_not_wide_open() {
    let capabilities = read_capabilities();
    for capability in capabilities {
        for permission in capability.permissions {
            for prefix in dangerous_permission_prefixes() {
                assert!(
                    !permission.starts_with(prefix),
                    "{} 不得授予危险插件权限 {}",
                    capability.identifier,
                    permission
                );
            }
        }
    }
}

#[test]
fn tauri_config_uses_only_explicit_capability_files() {
    let config_path = root().join("tauri.conf.json");
    let config: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(config_path).expect("读取 Tauri 配置"))
            .expect("解析 Tauri 配置");
    let configured = config
        .pointer("/app/security/capabilities")
        .and_then(|value| value.as_array())
        .expect("已配置 capabilities");
    let configured = configured
        .iter()
        .map(|value| value.as_str().expect("capability id 字符串").to_string())
        .collect::<BTreeSet<_>>();

    let actual = fs::read_dir(root().join("capabilities"))
        .expect("capabilities 目录存在")
        .filter_map(|entry| {
            let path = entry.ok()?.path();
            if path.extension().and_then(|ext| ext.to_str()) == Some("json") {
                Some(file_stem(&path))
            } else {
                None
            }
        })
        .collect::<BTreeSet<_>>();

    assert_eq!(configured, actual);
}

fn file_stem(path: &Path) -> String {
    path.file_stem()
        .and_then(|stem| stem.to_str())
        .expect("文件 stem")
        .to_string()
}
