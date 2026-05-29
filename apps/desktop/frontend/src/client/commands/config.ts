import { invokeCommand } from "../tauriClient";
import type { CommandOptions, ConfigSnapshot } from "../types/rpc";

interface RustConfigSnapshot {
  scope?: string;
  redacted?: boolean;
  values?: Record<string, string>;
}

function numberFromValue(values: Record<string, string> | undefined, key: string, fallback: number): number {
  const raw = values?.[key];
  if (raw === undefined) {
    return fallback;
  }
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function normalizeConfigSnapshot(raw: ConfigSnapshot | RustConfigSnapshot): ConfigSnapshot {
  if ("system" in raw && raw.system) {
    return raw as ConfigSnapshot;
  }

  const values = (raw as RustConfigSnapshot).values ?? {};
  return {
    version: numberFromValue(values, "version", 1),
    system: {
      theme: values["system.theme"] ?? "sakura",
      font_family: values["system.font_family"] ?? "Microsoft YaHei UI",
      font_scale: numberFromValue(values, "system.font_scale", 1.3),
      bubble_scale: numberFromValue(values, "system.bubble_scale", 1)
    }
  };
}

export async function getAllConfig(options?: CommandOptions): Promise<ConfigSnapshot> {
  const raw = await invokeCommand<ConfigSnapshot | RustConfigSnapshot>("config.get_all", {}, options);
  return normalizeConfigSnapshot(raw);
}

export function saveSystemConfig(
  snapshot: ConfigSnapshot,
  options?: CommandOptions
): Promise<{ applied_version: number; changed_scopes: string[] }> {
  return invokeCommand<{ applied_version: number; changed_scopes: string[] }>("config.save_system", {
    draft: snapshot.system,
    base_version: snapshot.version,
    confirm_token: "ui-system-settings"
  }, options);
}
