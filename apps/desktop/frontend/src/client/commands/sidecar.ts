import { invokeCommand } from "../tauriClient";
import type { CommandOptions, SidecarHello } from "../types/rpc";

interface SidecarHelloRaw {
  ready?: boolean;
  protocol_version?: 1;
  selected_protocol_version?: number;
  schema_hash?: string;
  capabilities?: string[];
  runtime_paths_ready?: boolean;
}

interface SidecarHealthRaw {
  healthy?: boolean;
  status?: string;
}

interface CancelRaw {
  request_id?: string;
  target_request_id?: string;
  status?: "cancelled" | "done" | "error" | "not_found" | "already_terminal";
  terminal_state?: "cancelled" | "done" | "error" | "not_found" | "already_terminal";
}

export async function sidecarHello(options?: CommandOptions): Promise<SidecarHello> {
  const raw = await invokeCommand<SidecarHelloRaw>("sidecar.hello", {}, options);
  return {
    ready: raw.ready ?? raw.runtime_paths_ready ?? false,
    protocol_version: 1,
    schema_hash: raw.schema_hash ?? "",
    capabilities: raw.capabilities ?? []
  };
}

export async function sidecarHealth(options?: CommandOptions): Promise<{ healthy: boolean }> {
  const raw = await invokeCommand<SidecarHealthRaw>("sidecar.health", {}, options);
  return {
    healthy: raw.healthy ?? raw.status === "healthy"
  };
}

export async function cancelRequest(
  request_id: string,
  options?: CommandOptions
): Promise<{ request_id: string; status: "cancelled" | "done" | "error" | "not_found" }> {
  let raw: CancelRaw;
  try {
    raw = await invokeCommand<CancelRaw>("sidecar.cancel", { request_id }, options);
  } catch (error) {
    if (typeof error === "object" && error !== null && (error as { code?: unknown }).code === "sidecar.task_not_found") {
      return { request_id, status: "not_found" };
    }
    throw error;
  }
  const status = raw.terminal_state ?? raw.status ?? "not_found";
  return {
    request_id: raw.target_request_id ?? raw.request_id ?? request_id,
    status: status === "already_terminal" ? "done" : status
  };
}
