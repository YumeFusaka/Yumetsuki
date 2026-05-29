import { subscribeEvent } from "../tauriClient";
import type { RpcError, RpcEvent, UnlistenFn } from "../types/rpc";

export interface DiagnosticDonePayload {
  report_id?: string;
  report_handle?: string;
  export_handle?: string;
  summary?: {
    report_id?: string;
    report_handle?: string;
    export_handle?: string;
  };
}

export function onDiagnosticsProgress(
  handler: (event: RpcEvent<{ percent?: number; progress?: number; summary?: string }>) => void
): Promise<UnlistenFn> {
  return subscribeEvent("diagnostic.progress", handler);
}

export function onDiagnosticsDone(handler: (event: RpcEvent<DiagnosticDonePayload>) => void): Promise<UnlistenFn> {
  return subscribeEvent("diagnostic.done", handler);
}

export function onDiagnosticsError(handler: (event: RpcEvent<{ error: RpcError }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("diagnostic.error", handler);
}
