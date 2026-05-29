import { subscribeEvent } from "../tauriClient";
import type { RpcError, RpcEvent, UnlistenFn } from "../types/rpc";

export function onMcpStatus(handler: (event: RpcEvent<{ status: Record<string, unknown> }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("mcp.status", handler);
}

export function onMcpDone(handler: (event: RpcEvent<{ summary?: Record<string, unknown> }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("mcp.done", handler);
}

export function onMcpToolStarted(handler: (event: RpcEvent<{ summary?: Record<string, unknown> }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("mcp.tool_started", handler);
}

export function onMcpToolDone(handler: (event: RpcEvent<{ summary?: Record<string, unknown> }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("mcp.tool_done", handler);
}

export function onMcpError(handler: (event: RpcEvent<{ error: RpcError }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("mcp.error", handler);
}

export function onMcpCancelled(handler: (event: RpcEvent<{ summary?: Record<string, unknown> }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("mcp.cancelled", handler);
}
