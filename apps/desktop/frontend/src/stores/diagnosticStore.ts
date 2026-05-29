import { defineStore } from "pinia";
import { exportDiagnostics, runDiagnostics } from "@/client/commands";
import { onDiagnosticsDone, onDiagnosticsError, onDiagnosticsProgress } from "@/client/events";
import type { RpcAccepted, RpcError, RpcEvent, UnlistenFn } from "@/client/types/rpc";
import { createRpcError } from "@/client/types/rpc";
import {
  createLifecycleState,
  disposeLifecycle,
  initLifecycle,
  restartLifecycle,
  trackSubscription
} from "./lifecycle";

interface DiagnosticDonePayload {
  report_id?: string;
  report_handle?: string;
  export_handle?: string;
  summary?: {
    report_id?: string;
    report_handle?: string;
    export_handle?: string;
  };
}

function normalizeProgressValue(
  payload: { percent?: number; progress?: number },
  fallback: number
): number {
  if (payload.percent !== undefined) {
    return Number.isFinite(payload.percent) ? payload.percent : fallback;
  }
  const value = payload.progress;
  if (value === undefined || !Number.isFinite(value)) {
    return fallback;
  }
  return value <= 1 ? Math.round(value * 100) : value;
}

function extractReportHandle(payload: DiagnosticDonePayload): string | null {
  return payload.report_handle ?? payload.summary?.report_handle ?? payload.report_id ?? payload.summary?.report_id ?? null;
}

function extractExportHandle(payload: DiagnosticDonePayload): string | null {
  return payload.export_handle ?? payload.summary?.export_handle ?? null;
}

export const useDiagnosticStore = defineStore("diagnosticStore", {
  state: () => ({
    lifecycle: createLifecycleState(),
    status: "idle" as "idle" | "running" | "cancelling" | "failed" | "exported" | "redaction-failed",
    recentChecks: ["sidecar", "config", "logs"] as string[],
    exportFormat: "zip" as "zip" | "json",
    currentRequest: null as RpcAccepted | null,
    exportRequest: null as RpcAccepted | null,
    progress: 0,
    summary: "",
    reportHandle: null as string | null,
    exportHandle: null as string | null,
    error: null as RpcError | null
  }),
  getters: {
    running: (state) => state.status === "running" || state.status === "cancelling",
    exporting: (state) => Boolean(state.exportRequest),
    canCancel: (state) => state.status === "running"
  },
  actions: {
    async init() {
      if (!initLifecycle(this.lifecycle)) {
        return;
      }
      const subscriptions: UnlistenFn[] = [
        await onDiagnosticsProgress((event) => this.applyProgress(event)),
        await onDiagnosticsDone((event) => this.applyDone(event)),
        await onDiagnosticsError((event) => this.applyError(event))
      ];
      for (const unsubscribe of subscriptions) {
        trackSubscription(this.lifecycle, unsubscribe);
      }
    },
    async run() {
      this.status = "running";
      this.progress = 0;
      this.error = null;
      this.reportHandle = null;
      this.exportHandle = null;
      this.currentRequest = await runDiagnostics();
    },
    async exportReport() {
      if (!this.reportHandle) {
        return;
      }
      this.exportRequest = await exportDiagnostics(this.exportFormat, this.reportHandle);
    },
    applyProgress(event: RpcEvent<{ percent?: number; progress?: number; summary?: string }>) {
      const activeRequestId = this.currentRequest?.request_id ?? this.exportRequest?.request_id ?? null;
      if (!activeRequestId || event.request_id !== activeRequestId) {
        return;
      }
      this.progress = normalizeProgressValue(event.payload, this.progress);
      this.summary = event.payload.summary ?? this.summary;
    },
    applyDone(event: RpcEvent<DiagnosticDonePayload>) {
      if (this.currentRequest && event.request_id === this.currentRequest.request_id) {
        this.status = "exported";
        this.reportHandle = extractReportHandle(event.payload);
        this.currentRequest = null;
        return;
      }
      if (!this.exportRequest || event.request_id !== this.exportRequest.request_id) {
        return;
      }
      this.status = "exported";
      this.exportHandle = extractExportHandle(event.payload);
      this.exportRequest = null;
    },
    applyError(event: RpcEvent<{ error: RpcError }>) {
      if (this.currentRequest && event.request_id === this.currentRequest.request_id) {
        this.status = event.payload.error.code === "diagnostics.redaction_failed" ? "redaction-failed" : "failed";
        this.error = event.payload.error;
        this.reportHandle = null;
        this.exportHandle = null;
        this.currentRequest = null;
        return;
      }
      if (!this.exportRequest || event.request_id !== this.exportRequest.request_id) {
        return;
      }
      this.status = event.payload.error.code === "diagnostics.redaction_failed" ? "redaction-failed" : "failed";
      this.error = event.payload.error;
      this.exportRequest = null;
      this.exportHandle = null;
    },
    dispose() {
      disposeLifecycle(this.lifecycle);
    },
    resetOnSidecarRestart() {
      restartLifecycle(this.lifecycle);
      if (this.currentRequest) {
        this.status = "failed";
        this.error = createRpcError("sidecar.restarted", "sidecar 已重启，诊断任务已停止。", {}, true);
      }
      this.currentRequest = null;
      this.exportRequest = null;
      this.reportHandle = null;
      this.exportHandle = null;
    }
  }
});
