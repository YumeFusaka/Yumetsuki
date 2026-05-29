include!("src/command_catalog.rs");

fn main() {
    tauri_build::try_build(
        tauri_build::Attributes::new()
            .app_manifest(tauri_build::AppManifest::new().commands(REGISTERED_COMMANDS)),
    )
    .expect("生成 Tauri 应用 manifest 失败");
}
