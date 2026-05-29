import { subscribeEvent } from "../tauriClient";
import type { RpcEvent, UnlistenFn } from "../types/rpc";

export function onSidecarExiting(handler: (event: RpcEvent<{ state: string }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("sidecar.exiting", handler);
}

export function onSidecarRestarted(
  handler: (event: RpcEvent<{ reason: string }>) => void
): Promise<UnlistenFn> {
  return subscribeEvent("sidecar.restarted", handler);
}

export function onSidecarCrashed(
  handler: (event: RpcEvent<{ summary: Record<string, unknown> }>) => void
): Promise<UnlistenFn> {
  return subscribeEvent("sidecar.crashed", handler);
}
