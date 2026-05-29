import { defineStore } from "pinia";
import { createLifecycleState, disposeLifecycle, initLifecycle, restartLifecycle } from "./lifecycle";

export const useWindowStore = defineStore("windowStore", {
  state: () => ({
    lifecycle: createLifecycleState(),
    position: { x: 80, y: 80 },
    size: { width: 1180, height: 760 },
    scale: 1,
    alwaysOnTop: false,
    transparent: false,
    dragging: false,
    trayOpen: false
  }),
  actions: {
    init() {
      initLifecycle(this.lifecycle);
    },
    dispose() {
      disposeLifecycle(this.lifecycle);
    },
    resetOnSidecarRestart() {
      restartLifecycle(this.lifecycle);
      this.dragging = false;
      this.trayOpen = false;
    },
    setScale(scale: number) {
      this.scale = Math.min(2, Math.max(0.75, scale));
    }
  }
});
