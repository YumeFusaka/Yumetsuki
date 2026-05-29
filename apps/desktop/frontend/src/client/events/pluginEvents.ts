import { subscribeEvent } from "../tauriClient";
import type { PluginStatus, RpcError, RpcEvent, UnlistenFn } from "../types/rpc";

export function onPluginStatus(handler: (event: RpcEvent<{ status: PluginStatus }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("plugin.status", handler);
}

export function onPluginImportProgress(handler: (event: RpcEvent<{ progress: number }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("plugin.import_progress", handler);
}

export function onPluginDone(handler: (event: RpcEvent<{ summary?: Record<string, unknown> }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("plugin.done", handler);
}

export function onPluginError(handler: (event: RpcEvent<{ error: RpcError }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("plugin.error", handler);
}

export function onPluginCancelled(handler: (event: RpcEvent<{ summary?: Record<string, unknown> }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("plugin.cancelled", handler);
}
