import { invokeCommand } from "../tauriClient";
import type { CommandOptions, PluginStatus, RpcAccepted } from "../types/rpc";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function normalizePluginStatus(value: unknown): PluginStatus {
  const record = isRecord(value) ? value : {};
  return {
    plugin_id: String(record.plugin_id ?? "example-plugin"),
    enabled: record.enabled !== false,
    loaded: record.loaded !== false,
    worker_state: String(record.worker_state ?? (record.enabled === false ? "disabled" : "idle"))
  };
}

export async function refreshPlugins(options?: CommandOptions): Promise<RpcAccepted> {
  return invokeCommand<RpcAccepted>("plugins.refresh", {}, options);
}

export async function getPluginStatus(
  plugin_id?: string | null,
  options?: CommandOptions
): Promise<{ status: PluginStatus }> {
  const raw = await invokeCommand<{ status?: unknown }>(
    "plugins.status",
    { plugin_id: plugin_id ?? null },
    options
  );
  return { status: normalizePluginStatus(raw.status) };
}

export function enablePlugin(plugin_id: string, confirm_token: string, options?: CommandOptions): Promise<{ enabled: boolean }> {
  return invokeCommand<{ enabled: boolean }>("plugins.enable", { plugin_id, confirm_token }, options);
}

export function disablePlugin(plugin_id: string, options?: CommandOptions): Promise<{ disabled: boolean }> {
  return invokeCommand<{ disabled: boolean }>("plugins.disable", { plugin_id }, options);
}
