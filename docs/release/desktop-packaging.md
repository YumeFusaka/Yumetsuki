# Tauri 桌面打包与发布安全

> 状态：Tauri 发布 gate 已启用。历史 PySide6 入口、旧 `ui/` 主实现和 PySide6 依赖已退场。

## 目标

Tauri 桌面包必须可复现、可扫描、可在干净 Windows 环境启动，并且不携带真实运行期数据或历史 PySide6 运行时。具体命令在 `apps/desktop/`、`python_core/` 和 `requirements-sidecar.txt` 落地后成为发布阻塞 gate。

## 工具链锁定

- Python 版本必须写入 `release_manifest.json` 的 `build_inputs.python_version`。
- Node 版本必须写入 `build_inputs.node_version`，并与 `apps/desktop/package-lock.json`、`pnpm-lock.yaml` 或项目选定 lockfile 一起校验。
- Rust toolchain 必须写入 `build_inputs.rust_version`，`apps/desktop/src-tauri/Cargo.lock` 必须提交并参与 hash 校验。
- Tauri 版本必须写入 `build_inputs.tauri_version`，Tauri capability manifest 的 hash 必须写入 `build_inputs.capability_manifest_hash` 和 `artifact_hashes.capability_manifest`。

## Python Sidecar 依赖

- 发布依赖入口是 `requirements-sidecar.txt`，不是 legacy `requirements.txt`。
- `requirements.txt` 仅作为历史兼容入口，不作为发布侧 sidecar 依赖来源。
- 发布 gate 禁止从 `requirements.txt` 打包 PySide6、Qt、QtWebEngine 或旧 `ui/` 主实现。
- `requirements-sidecar.txt` 必须只包含 headless sidecar 运行所需依赖，并由 `release_manifest.json` 记录 hash。

## 前端与 Rust Lock

- Node lockfile 必须提交并作为发布输入；未提交 lockfile 时发布可复现检查失败。
- `Cargo.lock` 必须提交，Tauri 插件和 Rust crate 升级必须伴随 lockfile 更新。
- 同一发布输入重复打包时，除 `generated_at` 等允许变动字段外，manifest 中稳定字段必须一致。

## Sidecar 与 Resources

- Python sidecar 构建产物必须嵌入或伴随 RPC schema hash。
- 只读默认资源放入 resources；首次启动只能复制 example/default 配置到 per-user app data。
- 不允许发布包携带真实 `data/config/api.yaml`、`data/config/memory.yaml`、日志、截图、浏览器 profile、记忆库或模型缓存。

## Native DLL / Wheel

- 只允许包含 sidecar 必需的 native DLL / wheel。
- 禁止 Qt DLL、PySide6 wheel、Qt plugin、QtWebEngine 和旧 `ui/` 运行时代码进入生产 bundle。
- onnxruntime、faster-whisper 等 native 依赖必须通过 manifest 记录来源和 hash。

## Playwright 策略

- Playwright browser 只属于 E2E / smoke 依赖，不进入生产 bundle。
- Web 自动化运行期如需浏览器，由用户本机环境或明确安装步骤提供，不把测试浏览器作为产品资源打包。

## Windows 干净机 Smoke

发布候选必须在无仓库、无开发环境、无 PySide6 环境变量的 Windows 干净机或等价沙箱中验证：

- 安装包可启动。
- Tauri shell ready。
- sidecar hello 成功或进入可解释 degraded 状态。
- 设置读取与默认配置复制成功。
- 聊天最小闭环可运行。
- 日志打开正常。
- 关闭时 sidecar、插件、MCP、临时句柄和临时音频清理完成。

## 发布扫描 Gate

基础命令：

```powershell
python scripts/check_release_manifest.py --bundle apps/desktop/src-tauri/target/release/bundle
python scripts/check_release_forbidden_content.py --bundle apps/desktop/src-tauri/target/release/bundle
python scripts/check_release_reproducibility.py --bundle apps/desktop/src-tauri/target/release/bundle
python scripts/check_final_capabilities_match_build.py --bundle apps/desktop/src-tauri/target/release/bundle
python scripts/check_perf_budgets.py
```

bundle 尚未生成时，开发测试可以使用临时 fake bundle 或显式 `--allow-missing`；发布 gate 不允许跳过。

## 依赖升级流程

1. 记录升级前 baseline：lockfile hash、manifest hash、性能预算结果和干净机 smoke 结果。
2. 升级 Python / Node / Rust / Tauri 依赖并更新对应 lockfile。
3. 重新运行发布包扫描、可复现检查、性能预算和 Windows 干净机 smoke。
4. 任一 gate 失败时先回滚 lockfile 和依赖变更，再拆分修复。
5. 通过后同步更新本文档、`release_manifest.json` 生成逻辑和相关测试。
