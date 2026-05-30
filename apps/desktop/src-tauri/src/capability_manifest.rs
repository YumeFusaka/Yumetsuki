pub const WINDOW_CAPABILITIES: &[&str] = &["main", "pet", "settings", "diagnostics"];

pub const PET_COMMANDS: &[&str] = &["window_drag", "window_resize", "chat_send", "sidecar_cancel"];

pub fn capability_file_name(identifier: &str) -> Option<&'static str> {
    match identifier {
        "main" => Some("main.json"),
        "pet" => Some("pet.json"),
        "settings" => Some("settings.json"),
        "diagnostics" => Some("diagnostics.json"),
        _ => None,
    }
}
