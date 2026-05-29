import { defineStore } from "pinia";
import { callTool, listSecurityGrants, listTools, queryToolAudit } from "@/client/commands";
import { onToolAudit, onToolCancelled, onToolError, onToolResult, onToolStarted } from "@/client/events";
import type { RpcAccepted, RpcError, RpcEvent, SecurityGrant, ToolAuditEntry, ToolItem, UnlistenFn } from "@/client/types/rpc";
import { createLifecycleState, disposeLifecycle, initLifecycle, restartLifecycle } from "./lifecycle";
import { trackSubscription } from "./lifecycle";

type ToolPanelStatus = "idle" | "loading" | "running" | "failed";

function removeId(items: string[], id: string): void {
  const index = items.indexOf(id);
  if (index >= 0) {
    items.splice(index, 1);
  }
}

export const useToolStore = defineStore("toolStore", {
  state: () => ({
    lifecycle: createLifecycleState(),
    status: "idle" as ToolPanelStatus,
    filter: "all",
    grantSummaries: [] as string[],
    expandedIds: [] as string[],
    items: [] as ToolItem[],
    auditItems: [] as ToolAuditEntry[],
    grants: [] as SecurityGrant[],
    runningIds: [] as string[],
    pendingConfirmationIds: [] as string[],
    lastResult: "" as string,
    error: null as RpcError | null
  }),
  getters: {
    filteredItems: (state) =>
      state.items.filter((item) => {
        if (state.filter === "enabled") {
          return item.enabled;
        }
        if (state.filter === "disabled") {
          return !item.enabled;
        }
        if (state.filter === "confirmation") {
          return item.requires_confirmation;
        }
        return true;
      }),
    running: (state) => state.runningIds.length > 0,
    grantCount: (state) => state.grants.length
  },
  actions: {
    async init() {
      if (!initLifecycle(this.lifecycle)) {
        return;
      }
      const subscriptions: UnlistenFn[] = [
        await onToolStarted((event) => this.applyStarted(event)),
        await onToolAudit((event) => this.applyAudit(event)),
        await onToolResult((event) => this.applyResult(event)),
        await onToolError((event) => this.applyError(event)),
        await onToolCancelled((event) => this.applyCancelled(event))
      ];
      for (const unsubscribe of subscriptions) {
        trackSubscription(this.lifecycle, unsubscribe);
      }
      await this.reload();
    },
    async reload() {
      this.status = "loading";
      this.error = null;
      try {
        const [tools, audit, grants] = await Promise.all([
          listTools(true),
          queryToolAudit({ limit: 20 }),
          listSecurityGrants()
        ]);
        this.items = tools.items;
        this.auditItems = audit.items;
        this.grants = grants.grants;
        this.grantSummaries = this.grants.map((grant) => `${grant.capability}:${grant.scope_hash}`);
        this.status = this.running ? "running" : "idle";
      } catch (error) {
        this.status = "failed";
        this.error = error as RpcError;
      }
    },
    async runDryRun(tool_name: string) {
      this.status = "running";
      this.error = null;
      const accepted: RpcAccepted = await callTool({
        tool_name,
        source: "desktop.tools.panel",
        arguments: { value: "ping" },
        dry_run: true
      });
      if (!this.runningIds.includes(accepted.request_id)) {
        this.runningIds.push(accepted.request_id);
      }
    },
    applyStarted(event: RpcEvent<{ summary?: Record<string, unknown> }>) {
      if (!this.runningIds.includes(event.request_id)) {
        this.runningIds.push(event.request_id);
      }
      this.status = "running";
      const toolName = event.payload.summary?.tool_name;
      if (typeof toolName === "string") {
        this.lastResult = `${toolName} 开始执行`;
      }
    },
    applyAudit(event: RpcEvent<{ audit_summary?: Record<string, unknown> }>) {
      const summary = event.payload.audit_summary ?? {};
      this.auditItems.unshift({
        audit_entry_id: `event_${event.request_id}_${event.sequence}`,
        timestamp_ms: event.timestamp_ms,
        actor: "sidecar",
        action: "dry_run",
        allowed: summary.allowed !== false,
        tool_name: typeof summary.tool_name === "string" ? summary.tool_name : undefined
      });
      this.auditItems.splice(20);
    },
    applyResult(event: RpcEvent<{ summary?: Record<string, unknown> }>) {
      removeId(this.runningIds, event.request_id);
      const toolName = event.payload.summary?.tool_name;
      this.lastResult = typeof toolName === "string" ? `${toolName} dry-run 完成` : "工具 dry-run 完成";
      this.status = this.running ? "running" : "idle";
    },
    applyError(event: RpcEvent<{ error: RpcError }>) {
      removeId(this.runningIds, event.request_id);
      this.status = "failed";
      this.error = event.payload.error;
    },
    applyCancelled(event: RpcEvent<{ summary?: Record<string, unknown> }>) {
      removeId(this.runningIds, event.request_id);
      this.status = this.running ? "running" : "idle";
      this.lastResult = "工具调用已取消";
    },
    dispose() {
      disposeLifecycle(this.lifecycle);
    },
    resetOnSidecarRestart() {
      restartLifecycle(this.lifecycle);
      this.runningIds = [];
      this.pendingConfirmationIds = [];
      this.status = "idle";
      this.lastResult = "";
      this.error = null;
    }
  }
});
