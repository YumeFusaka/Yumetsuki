import { subscribeEvent } from "../tauriClient";
import type { RpcError, RpcEvent, UnlistenFn } from "../types/rpc";

export function onToolStarted(handler: (event: RpcEvent<{ summary?: Record<string, unknown> }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("tool.started", handler);
}

export function onToolResult(handler: (event: RpcEvent<{ summary?: Record<string, unknown> }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("tool.result", handler);
}

export function onToolError(handler: (event: RpcEvent<{ error: RpcError }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("tool.error", handler);
}

export function onToolCancelled(handler: (event: RpcEvent<{ summary?: Record<string, unknown> }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("tool.cancelled", handler);
}

export function onToolAudit(handler: (event: RpcEvent<{ audit_summary?: Record<string, unknown> }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("tool.audit", handler);
}
