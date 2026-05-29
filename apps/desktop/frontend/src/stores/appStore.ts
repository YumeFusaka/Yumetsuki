import { defineStore } from "pinia";
import { onSidecarRestarted } from "@/client/events";
import { sidecarHello } from "@/client/commands";
import type { RpcError, UnlistenFn } from "@/client/types/rpc";
import { createRpcError } from "@/client/types/rpc";
import {
  createLifecycleState,
  disposeLifecycle,
  initLifecycle,
  restartLifecycle,
  trackSubscription
} from "./lifecycle";

export type StartupStatus = "frontend_loaded" | "sidecar_starting" | "handshake" | "ready" | "degraded" | "failed";

export const useAppStore = defineStore("appStore", {
  state: () => ({
    lifecycle: createLifecycleState(),
    startupStatus: "frontend_loaded" as StartupStatus,
    sidecarStatus: "starting" as "starting" | "ready" | "degraded" | "failed",
    schemaHash: "",
    capabilities: [] as string[],
    globalError: null as RpcError | null,
    runningRequestIds: [] as string[],
    startupPreference: {
      openLastRoute: true
    }
  }),
  getters: {
    isReady: (state) => state.sidecarStatus === "ready",
    statusText: (state) => {
      if (state.sidecarStatus === "starting") {
        return "sidecar 启动中";
      }
      if (state.sidecarStatus === "ready") {
        return "sidecar 已就绪";
      }
      if (state.sidecarStatus === "degraded") {
        return "sidecar 已降级";
      }
      return "sidecar 不可用";
    }
  },
  actions: {
    async init() {
      if (!initLifecycle(this.lifecycle)) {
        return;
      }
      this.startupStatus = "sidecar_starting";
      const restartUnlisten: UnlistenFn = await onSidecarRestarted(() => this.resetOnSidecarRestart());
      trackSubscription(this.lifecycle, restartUnlisten);
      await this.bootstrap();
    },
    async bootstrap() {
      this.startupStatus = "handshake";
      this.sidecarStatus = "starting";
      try {
        const hello = await sidecarHello();
        this.schemaHash = hello.schema_hash;
        this.capabilities = hello.capabilities;
        this.sidecarStatus = hello.ready ? "ready" : "degraded";
        this.startupStatus = hello.ready ? "ready" : "degraded";
      } catch (error) {
        this.globalError = createRpcError("sidecar.not_ready", "sidecar 暂不可用。", { error: String(error) }, true);
        this.sidecarStatus = "degraded";
        this.startupStatus = "degraded";
      }
    },
    dispose() {
      disposeLifecycle(this.lifecycle);
    },
    resetOnSidecarRestart() {
      restartLifecycle(this.lifecycle);
      this.sidecarStatus = "degraded";
      this.startupStatus = "degraded";
      this.runningRequestIds = [];
      this.globalError = createRpcError("sidecar.restarted", "sidecar 已重启，运行中的请求已停止。", {}, true);
    }
  }
});
