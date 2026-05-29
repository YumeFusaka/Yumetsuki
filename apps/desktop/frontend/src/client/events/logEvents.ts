import { subscribeEvent } from "../tauriClient";
import type { LogEntry, RpcEvent, UnlistenFn } from "../types/rpc";

export function onLogBatch(handler: (event: RpcEvent<{ entries: LogEntry[] }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("log.batch", handler);
}
