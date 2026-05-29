import { defineStore } from "pinia";
import { getAllConfig, saveSystemConfig } from "@/client/commands";
import type { ConfigSnapshot, RpcError } from "@/client/types/rpc";
import { createRpcError } from "@/client/types/rpc";
import { createLifecycleState, disposeLifecycle, initLifecycle, restartLifecycle } from "./lifecycle";

const emptySnapshot: ConfigSnapshot = {
  version: 0,
  system: {
    theme: "sakura",
    font_family: "Microsoft YaHei UI",
    font_scale: 1.3,
    bubble_scale: 1
  }
};

export const useConfigStore = defineStore("configStore", {
  state: () => ({
    lifecycle: createLifecycleState(),
    snapshot: emptySnapshot as ConfigSnapshot,
    draft: emptySnapshot as ConfigSnapshot,
    dirty: false,
    saving: false,
    needsReload: false,
    error: null as RpcError | null
  }),
  actions: {
    async init() {
      if (!initLifecycle(this.lifecycle)) {
        return;
      }
      await this.load();
    },
    async load() {
      try {
        this.snapshot = await getAllConfig();
        this.draft = structuredClone(this.snapshot);
        this.dirty = false;
        this.needsReload = false;
      } catch (error) {
        this.error = createRpcError("config.read_failed", "配置读取失败。", { error: String(error) }, true);
      }
    },
    editDraft(fontScale: number) {
      this.draft.system.font_scale = fontScale;
      this.dirty = true;
    },
    async saveSystem() {
      this.saving = true;
      this.error = null;
      try {
        const result = await saveSystemConfig(this.draft);
        this.snapshot = structuredClone(this.draft);
        this.snapshot.version = result.applied_version;
        this.draft.version = result.applied_version;
        this.dirty = false;
        this.needsReload = false;
      } catch (error) {
        this.error = createRpcError("config.write_failed", "配置保存失败。", { error: String(error) }, true);
      } finally {
        this.saving = false;
      }
    },
    dispose() {
      disposeLifecycle(this.lifecycle);
    },
    resetOnSidecarRestart() {
      restartLifecycle(this.lifecycle);
      this.saving = false;
      this.needsReload = true;
    }
  }
});
