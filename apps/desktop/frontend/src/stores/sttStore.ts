import { defineStore } from "pinia";
import { createLifecycleState, disposeLifecycle, initLifecycle, restartLifecycle } from "./lifecycle";

export const useSttStore = defineStore("sttStore", {
  state: () => ({
    lifecycle: createLifecycleState(),
    recording: false,
    transcribing: false,
    canRetry: false,
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
      this.recording = false;
      this.transcribing = false;
      this.canRetry = true;
      this.error = "sidecar.restarted";
    }
  }
});
