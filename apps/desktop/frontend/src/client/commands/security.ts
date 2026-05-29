import { invokeCommand } from "../tauriClient";
import type { CommandOptions, SecurityGrant } from "../types/rpc";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function normalizeGrant(value: unknown): SecurityGrant {
  const record = isRecord(value) ? value : {};
  return {
    grant_id: String(record.grant_id ?? "grant-unknown"),
    capability: String(record.capability ?? "unknown"),
    scope_hash: String(record.scope_hash ?? "unknown")
  };
}

export async function listSecurityGrants(
  filters: Record<string, unknown> | null = null,
  options?: CommandOptions
): Promise<{ grants: SecurityGrant[] }> {
  const raw = await invokeCommand<{ grants?: unknown[] }>("security.list_grants", { filters }, options);
  return { grants: (raw.grants ?? []).map(normalizeGrant) };
}
