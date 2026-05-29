import { defineStore } from "pinia";
import { queryLogs } from "@/client/commands";
import { onLogBatch } from "@/client/events";
import type { LogEntry, UnlistenFn } from "@/client/types/rpc";
import {
  createLifecycleState,
  disposeLifecycle,
  initLifecycle,
  restartLifecycle,
  trackSubscription
} from "./lifecycle";

export const useLogStore = defineStore("logStore", {
  state: () => ({
    lifecycle: createLifecycleState(),
    channel: "system" as "conversation" | "system",
    source: "all",
    level: "all",
    followBottom: true,
    columnWidths: { time: 96, level: 72, source: 160 },
    entries: [] as LogEntry[],
    selectedDetail: null as LogEntry | null,
    selectionActive: false
  }),
  getters: {
    filtered: (state) =>
      state.entries.filter((entry) => {
        const levelMatches = state.level === "all" || entry.level === state.level;
        const sourceMatches = state.source === "all" || entry.source === state.source;
        return levelMatches && sourceMatches;
      })
  },
  actions: {
    async init() {
      if (!initLifecycle(this.lifecycle)) {
        return;
      }
      const unlisten: UnlistenFn = await onLogBatch((event) => this.appendBatch(event.payload.entries));
      trackSubscription(this.lifecycle, unlisten);
      const result = await queryLogs({ channel: this.channel, limit: 100 });
      this.appendBatch(result.entries);
    },
    appendBatch(entries: LogEntry[]) {
      this.entries.push(...entries);
      if (this.entries.length > 1000) {
        this.entries.splice(0, this.entries.length - 1000);
      }
    },
    pauseForSelection(active: boolean) {
      this.selectionActive = active;
    },
    dispose() {
      disposeLifecycle(this.lifecycle);
    },
    resetOnSidecarRestart() {
      restartLifecycle(this.lifecycle);
      disposeLifecycle(this.lifecycle);
    }
  }
});
