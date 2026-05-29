import { defineStore } from "pinia";
import { createRpcError } from "@/client/types/rpc";
import { disablePlugin, enablePlugin, getPluginStatus, refreshPlugins } from "@/client/commands";
import { onPluginCancelled, onPluginDone, onPluginError, onPluginImportProgress, onPluginStatus } from "@/client/events";
import type { PluginStatus, RpcAccepted, RpcError, RpcEvent, UnlistenFn } from "@/client/types/rpc";
import {
  createLifecycleState,
  disposeLifecycle,
  initLifecycle,
  restartLifecycle,
  trackSubscription
} from "./lifecycle";

type PluginPanelStatus = "idle" | "loading" | "refreshing" | "failed";

function upsertStatus(items: PluginStatus[], status: PluginStatus): void {
  const index = items.findIndex((item) => item.plugin_id === status.plugin_id);
  if (index >= 0) {
    items[index] = status;
  } else {
    items.push(status);
  }
}

export const usePluginStore = defineStore("pluginStore", {
  state: () => ({
    lifecycle: createLifecycleState(),
    status: "idle" as PluginPanelStatus,
    filter: "all",
    expandedIds: [] as string[],
    enabledPluginIds: [] as string[],
    items: [] as PluginStatus[],
    confirmTokens: {} as Record<string, string>,
    scanning: false,
    importing: false,
    importProgress: 0,
    activeRequest: null as RpcAccepted | null,
    lastSummary: "" as string,
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
        if (state.filter === "loaded") {
          return item.loaded;
        }
        return true;
      })
  },
  actions: {
    async init() {
      if (!initLifecycle(this.lifecycle)) {
        return;
      }
      const subscriptions: UnlistenFn[] = [
        await onPluginStatus((event) => this.applyStatus(event)),
        await onPluginImportProgress((event) => this.applyProgress(event)),
        await onPluginDone((event) => this.applyDone(event)),
        await onPluginError((event) => this.applyError(event)),
        await onPluginCancelled((event) => this.applyCancelled(event))
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
        const result = await getPluginStatus();
        upsertStatus(this.items, result.status);
        this.enabledPluginIds = this.items.filter((item) => item.enabled).map((item) => item.plugin_id);
        this.status = "idle";
      } catch (error) {
        this.status = "failed";
        this.error = error as RpcError;
      }
    },
    async refresh() {
      this.status = "refreshing";
      this.scanning = true;
      this.error = null;
      this.activeRequest = await refreshPlugins();
    },
    setEnableConfirmToken(plugin_id: string, value: string) {
      this.confirmTokens[plugin_id] = value;
    },
    async enable(plugin_id: string) {
      this.error = null;
      const confirm_token = this.confirmTokens[plugin_id]?.trim();
      if (!confirm_token) {
        this.status = "failed";
        this.error = createRpcError("rpc.invalid_params", "请先输入确认令牌。", { field: "confirm_token" }, false);
        return;
      }
      const result = await enablePlugin(plugin_id, confirm_token);
      if (result.enabled && !this.enabledPluginIds.includes(plugin_id)) {
        this.enabledPluginIds.push(plugin_id);
      }
      delete this.confirmTokens[plugin_id];
      this.lastSummary = `${plugin_id} 已启用`;
      this.status = "idle";
    },
    async disable(plugin_id: string) {
      this.error = null;
      const result = await disablePlugin(plugin_id);
      if (result.disabled) {
        this.enabledPluginIds = this.enabledPluginIds.filter((id) => id !== plugin_id);
      }
      this.lastSummary = `${plugin_id} 已停用`;
      this.status = "idle";
    },
    applyStatus(event: RpcEvent<{ status: PluginStatus }>) {
      upsertStatus(this.items, event.payload.status);
      this.enabledPluginIds = this.items.filter((item) => item.enabled).map((item) => item.plugin_id);
    },
    applyProgress(event: RpcEvent<{ progress: number }>) {
      this.importing = true;
      const progress = Number.isFinite(event.payload.progress) ? event.payload.progress : 0;
      this.importProgress = progress <= 1 ? Math.round(progress * 100) : progress;
    },
    applyDone(event: RpcEvent<{ summary?: Record<string, unknown> }>) {
      if (this.activeRequest?.request_id === event.request_id) {
        this.activeRequest = null;
      }
      this.scanning = false;
      this.importing = false;
      this.importProgress = 100;
      const pluginCount = event.payload.summary?.plugin_count;
      this.lastSummary = typeof pluginCount === "number" ? `已扫描 ${pluginCount} 个插件` : "插件任务完成";
      this.status = "idle";
    },
    applyError(event: RpcEvent<{ error: RpcError }>) {
      if (this.activeRequest?.request_id === event.request_id) {
        this.activeRequest = null;
      }
      this.scanning = false;
      this.importing = false;
      this.status = "failed";
      this.error = event.payload.error;
    },
    applyCancelled(event: RpcEvent<{ summary?: Record<string, unknown> }>) {
      if (this.activeRequest?.request_id === event.request_id) {
        this.activeRequest = null;
      }
      this.scanning = false;
      this.importing = false;
      this.status = "idle";
      this.lastSummary = "插件任务已取消";
    },
    dispose() {
      disposeLifecycle(this.lifecycle);
    },
    resetOnSidecarRestart() {
      restartLifecycle(this.lifecycle);
      this.scanning = false;
      this.importing = false;
      this.importProgress = 0;
      this.activeRequest = null;
      this.error = null;
      this.status = "idle";
      this.confirmTokens = {};
    }
  }
});
