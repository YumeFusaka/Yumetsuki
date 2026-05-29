import { invokeCommand } from "../tauriClient";
import type { CommandOptions, RpcAccepted } from "../types/rpc";

export function runDiagnostics(options?: CommandOptions): Promise<RpcAccepted> {
  return invokeCommand<RpcAccepted>("diagnostics.run", { checks: ["sidecar", "config", "logs"] }, options);
}

export function exportDiagnostics(
  format: "zip" | "json" = "zip",
  report_handle = "report_latest",
  options?: CommandOptions
): Promise<RpcAccepted> {
  return invokeCommand<RpcAccepted>("diagnostics.export", { format, report_handle }, options);
}
