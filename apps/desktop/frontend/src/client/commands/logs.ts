import { invokeCommand } from "../tauriClient";
import type { CommandOptions, LogEntry } from "../types/rpc";

export interface LogQueryParams {
  channel?: "conversation" | "system";
  level?: string;
  source?: string;
  limit?: number;
}

export function queryLogs(
  params: LogQueryParams = {},
  options?: CommandOptions
): Promise<{ entries: LogEntry[] }> {
  return invokeCommand<{ entries?: unknown[]; items?: unknown[] }, LogQueryParams>("logs.query", params, options).then((raw) => ({
    entries: (raw.entries ?? raw.items ?? []).map(normalizeLogEntry)
  }));
}

function normalizeLogEntry(entry: unknown, index: number): LogEntry {
  const record = typeof entry === "object" && entry !== null ? (entry as Record<string, unknown>) : {};
  const timestamp = typeof record.timestamp_ms === "number" ? record.timestamp_ms : Date.now();
  const level = normalizeLevel(record.level);
  return {
    id: String(record.id ?? `log_${timestamp}_${index}`),
    timestamp_ms: timestamp,
    level,
    source: String(record.source ?? "python_core.sidecar"),
    event_type: String(record.event_type ?? "platform"),
    summary: String(record.summary ?? record.message ?? ""),
    trace_id: typeof record.trace_id === "string" ? record.trace_id : undefined
  };
}

function normalizeLevel(level: unknown): LogEntry["level"] {
  if (level === "debug" || level === "info" || level === "warning" || level === "error") {
    return level;
  }
  return "info";
}
