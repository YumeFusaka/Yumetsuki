import { defineStore } from "pinia";
import { createLifecycleState, disposeLifecycle, initLifecycle, restartLifecycle } from "./lifecycle";

export const useCharacterStore = defineStore("characterStore", {
  state: () => ({
    lifecycle: createLifecycleState(),
    recentCharacterId: "default",
    displayPreferences: {
      showSprite: true
    },
    resourceState: "empty" as "empty" | "ready" | "stale"
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
      this.resourceState = "stale";
    }
  }
});
