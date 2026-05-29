import { defineStore } from "pinia";
import { createLifecycleState, disposeLifecycle, initLifecycle, restartLifecycle } from "./lifecycle";

export const useAudioStore = defineStore("audioStore", {
  state: () => ({
    lifecycle: createLifecycleState(),
    playing: false,
    queueSize: 0,
    error: null as string | null
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
      this.playing = false;
      this.queueSize = 0;
      this.error = "sidecar.restarted";
    }
  }
});
