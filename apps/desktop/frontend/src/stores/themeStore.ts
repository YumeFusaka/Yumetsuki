import { defineStore } from "pinia";
import { createLifecycleState, disposeLifecycle, initLifecycle, restartLifecycle } from "./lifecycle";

export const SAKURA_TOKENS = {
  accent: "#d4567a",
  accentStrong: "#9b3060",
  text: "#4a3040",
  textMuted: "#6b4a5a",
  surface: "rgba(255, 255, 255, 0.72)"
};

export const useThemeStore = defineStore("themeStore", {
  state: () => ({
    lifecycle: createLifecycleState(),
    themeName: "sakura",
    fontFamily: "Microsoft YaHei UI",
    fontScale: 1.3,
    bubbleScale: 1,
    tokens: SAKURA_TOKENS,
    tokenOverride: null as Partial<typeof SAKURA_TOKENS> | null,
    runtimeError: null as string | null
  }),
  getters: {
    effectiveTokens: (state) => ({ ...state.tokens, ...(state.tokenOverride ?? {}) })
  },
  actions: {
    init() {
      if (!initLifecycle(this.lifecycle)) {
        return;
      }
      this.applyTokens();
    },
    dispose() {
      disposeLifecycle(this.lifecycle);
    },
    resetOnSidecarRestart() {
      restartLifecycle(this.lifecycle);
      this.tokenOverride = null;
      this.applyTokens();
    },
    applyTokens() {
      if (typeof document === "undefined") {
        return;
      }
      const root = document.documentElement;
      const tokens = this.effectiveTokens;
      root.style.setProperty("--sakura-accent", tokens.accent);
      root.style.setProperty("--sakura-accent-strong", tokens.accentStrong);
      root.style.setProperty("--sakura-text", tokens.text);
      root.style.setProperty("--sakura-text-muted", tokens.textMuted);
      root.style.setProperty("--sakura-surface", tokens.surface);
      root.style.setProperty("--sakura-font-scale", String(this.fontScale));
    }
  }
});
