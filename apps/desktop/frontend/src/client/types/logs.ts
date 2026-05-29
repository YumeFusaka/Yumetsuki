import type { LogEntry } from "./rpc";

export type { LogEntry };

export interface LogQueryResult {
  entries: LogEntry[];
}
