import { defineStore } from "pinia";
import { callMcpTool, listMcpServers, refreshMcp } from "@/client/commands";
import { onMcpCancelled, onMcpDone, onMcpError, onMcpStatus, onMcpToolDone, onMcpToolStarted } from "@/client/events";
import type { McpServerSummary, RpcAccepted, RpcError, RpcEvent, UnlistenFn } from "@/client/types/rpc";
import {
  createLifecycleState,
  disposeLifecycle,
  initLifecycle,
  restartLifecycle,
  trackSubscription
} from "./lifecycle";

type McpPanelStatus = "idle" | "loading" | "refreshing" | "calling" | "failed";

function upsertServer(items: McpServerSummary[], patch: Partial<McpServerSummary> & { server_id: string }): void {
  const existing = items.find((item) => item.server_id === patch.server_id);
  if (existing) {
    Object.assign(existing, patch);
    return;
  }
  items.push({
    server_id: patch.server_id,
    enabled: patch.enabled ?? true,
    state: patch.state ?? "unknown",
    tool_count: patch.tool_count ?? 0
  });
}

export const useMcpStore = defineStore("mcpStore", {
  state: () => ({
    lifecycle: createLifecycleState(),
    status: "idle" as McpPanelStatus,
    filter: "all",
    expandedIds: [] as string[],
    serverSummaries: [] as string[],
    servers: [] as McpServerSummary[],
    connectingIds: [] as string[],
    runningIds: [] as string[],
    refreshing: false,
    activeRequest: null as RpcAccepted | null,
    lastToolResult: "" as string,
    error: null as RpcError | null
  }),
  getters: {
    filteredServers: (state) =>
      state.servers.filter((server) => {
        if (state.filter === "enabled") {
          return server.enabled;
        }
        if (state.filter === "disabled") {
          return !server.enabled;
        }
        if (state.filter === "ready") {
          return server.state === "ready";
        }
        return true;
      }),
    busy: (state) => state.refreshing || state.runningIds.length > 0
  },
  actions: {
    async init() {
      if (!initLifecycle(this.lifecycle)) {
        return;
      }
      const subscriptions: UnlistenFn[] = [
        await onMcpStatus((event) => this.applyStatus(event)),
        await onMcpToolStarted((event) => this.applyToolStarted(event)),
        await onMcpToolDone((event) => this.applyDone(event)),
        await onMcpDone((event) => this.applyDone(event)),
        await onMcpError((event) => this.applyError(event)),
        await onMcpCancelled((event) => this.applyCancelled(event))
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
        const result = await listMcpServers(true);
        this.servers = result.servers;
        this.serverSummaries = this.servers.map((server) => `${server.server_id}:${server.state}`);
        this.status = "idle";
      } catch (error) {
        this.status = "failed";
        this.error = error as RpcError;
      }
    },
    async refresh(server_id?: string) {
      this.status = "refreshing";
      this.refreshing = true;
      this.error = null;
      this.activeRequest = await refreshMcp(server_id ?? null);
      if (server_id && !this.connectingIds.includes(server_id)) {
        this.connectingIds.push(server_id);
      }
    },
    async callEcho(server_id: string) {
      this.status = "calling";
      this.error = null;
      const accepted = await callMcpTool(server_id, "echo", { value: "ping" });
      this.activeRequest = accepted;
      if (!this.runningIds.includes(accepted.request_id)) {
        this.runningIds.push(accepted.request_id);
      }
    },
    applyStatus(event: RpcEvent<{ status: Record<string, unknown> }>) {
      const status = event.payload.status;
      const serverId = typeof status.server_id === "string" ? status.server_id : "local-dev";
      upsertServer(this.servers, {
        server_id: serverId,
        state: typeof status.state === "string" ? status.state : "unknown"
      });
      this.serverSummaries = this.servers.map((server) => `${server.server_id}:${server.state}`);
    },
    applyToolStarted(event: RpcEvent<{ summary?: Record<string, unknown> }>) {
      if (!this.runningIds.includes(event.request_id)) {
        this.runningIds.push(event.request_id);
      }
      this.status = "calling";
      const serverId = event.payload.summary?.server_id;
      if (typeof serverId === "string") {
        upsertServer(this.servers, { server_id: serverId, state: "tool-running" });
      }
    },
    applyDone(event: RpcEvent<{ summary?: Record<string, unknown> }>) {
      this.runningIds = this.runningIds.filter((id) => id !== event.request_id);
      if (this.activeRequest?.request_id === event.request_id) {
        this.activeRequest = null;
      }
      const serverId = event.payload.summary?.server_id;
      if (typeof serverId === "string") {
        upsertServer(this.servers, { server_id: serverId, state: "ready" });
      }
      this.connectingIds = [];
      this.refreshing = false;
      this.lastToolResult = "MCP 调用完成";
      this.serverSummaries = this.servers.map((server) => `${server.server_id}:${server.state}`);
      this.status = this.runningIds.length > 0 ? "calling" : "idle";
    },
    applyError(event: RpcEvent<{ error: RpcError }>) {
      this.runningIds = this.runningIds.filter((id) => id !== event.request_id);
      this.connectingIds = [];
      this.refreshing = false;
      this.status = "failed";
      this.error = event.payload.error;
    },
    applyCancelled(event: RpcEvent<{ summary?: Record<string, unknown> }>) {
      this.runningIds = this.runningIds.filter((id) => id !== event.request_id);
      this.connectingIds = [];
      this.refreshing = false;
      this.status = "idle";
      this.lastToolResult = "MCP 任务已取消";
    },
    dispose() {
      disposeLifecycle(this.lifecycle);
    },
    resetOnSidecarRestart() {
      restartLifecycle(this.lifecycle);
      this.connectingIds = [];
      this.runningIds = [];
      this.refreshing = false;
      this.activeRequest = null;
      this.error = null;
      this.status = "idle";
    }
  }
});
