import { defineStore } from "pinia";
import { cancelRequest, sendChat } from "@/client/commands";
import { onChatCancelled, onChatDelta, onChatDone, onChatError } from "@/client/events";
import { createRequestId, createTraceId } from "@/client/id";
import { clearTrackedTask, getTrackedTask, markTerminalEvent, registerAcceptedTask } from "@/client/tauriClient";
import type { ChatMessage, RpcAccepted, RpcError, RpcEvent, UnlistenFn } from "@/client/types/rpc";
import { createRpcError } from "@/client/types/rpc";
import {
  createLifecycleState,
  disposeLifecycle,
  initLifecycle,
  restartLifecycle,
  trackSubscription
} from "./lifecycle";

function createUserMessage(content: string): ChatMessage {
  return {
    id: `msg_user_${Date.now().toString(36)}`,
    role: "user",
    content,
    status: "done"
  };
}

export const useChatStore = defineStore("chatStore", {
  state: () => ({
    lifecycle: createLifecycleState(),
    messages: [] as ChatMessage[],
    inputDraft: "",
    streamingDraft: "",
    pendingRequests: new Map<string, RpcAccepted>(),
    handledTerminalRequests: new Set<string>(),
    passiveMode: false,
    busy: false,
    statusText: "空闲",
    error: null as RpcError | null,
    lastFailedInput: ""
  }),
  getters: {
    canRetry: (state) => Boolean(state.error && state.lastFailedInput),
    activeRequestId: (state) => Array.from(state.pendingRequests.keys())[0] ?? null
  },
  actions: {
    async init() {
      if (!initLifecycle(this.lifecycle)) {
        return;
      }
      const subscriptions: UnlistenFn[] = [
        await onChatDelta((event) => this.applyDelta(event)),
        await onChatDone((event) => this.applyTerminal(event, "done")),
        await onChatError((event) => this.applyTerminal(event, "error")),
        await onChatCancelled((event) => this.applyTerminal(event, "cancelled"))
      ];
      for (const unsubscribe of subscriptions) {
        trackSubscription(this.lifecycle, unsubscribe);
      }
    },
    async send(message?: string) {
      const trimmed = (message ?? this.inputDraft).trim();
      if (!trimmed) {
        return;
      }
      this.error = null;
      this.messages.push(createUserMessage(trimmed));
      this.inputDraft = "";
      this.busy = true;
      this.statusText = "正在发送";
      const requestId = createRequestId();
      const traceId = createTraceId();
      const pending: RpcAccepted = {
        accepted: true,
        request_id: requestId,
        trace_id: traceId,
        parent_trace_id: null,
        session_id: "",
        task_type: "chat"
      };
      registerAcceptedTask(pending);
      this.pendingRequests.set(requestId, pending);

      try {
        const accepted = await sendChat({ message: trimmed }, { request_id: requestId, trace_id: traceId });
        const tracked = getTrackedTask(accepted.request_id);
        if (this.handledTerminalRequests.has(accepted.request_id) || tracked?.terminal_state) {
          this.pendingRequests.delete(accepted.request_id);
          this.busy = this.pendingRequests.size > 0;
          return;
        }
        this.pendingRequests.set(accepted.request_id, accepted);
        this.statusText = "回复生成中";
        this.streamingDraft = "";
      } catch (error) {
        this.pendingRequests.delete(requestId);
        clearTrackedTask(requestId);
        this.error = createRpcError("chat.send_failed", "发送失败，已保留输入。", { error: String(error) }, true);
        this.lastFailedInput = trimmed;
        this.inputDraft = trimmed;
        this.busy = false;
        this.statusText = "请求失败";
      }
    },
    async stop() {
      const requestId = this.activeRequestId;
      if (!requestId) {
        return;
      }
      this.statusText = "停止中";
      try {
        const result = await cancelRequest(requestId);
        if (result.status === "not_found") {
          this.pendingRequests.delete(requestId);
          this.busy = this.pendingRequests.size > 0;
          this.statusText = this.busy ? "回复生成中" : "已停止";
        }
      } catch (error) {
        const code = typeof error === "object" && error !== null ? (error as { code?: string }).code : undefined;
        if (code === "sidecar.busy") {
          this.statusText = this.pendingRequests.size > 0 ? "回复生成中" : "停止中";
          return;
        }
        this.error = createRpcError("chat.cancel_failed", "停止失败，请稍后重试。", { error: String(error) }, true);
        this.statusText = "停止失败";
      }
    },
    async retry() {
      if (!this.lastFailedInput) {
        return;
      }
      await this.send(this.lastFailedInput);
    },
    applyDelta(event: RpcEvent<{ text: string }>) {
      if (!this.pendingRequests.has(event.request_id) || this.handledTerminalRequests.has(event.request_id)) {
        return;
      }
      this.streamingDraft += event.payload.text;
      this.statusText = "回复生成中";
    },
    applyTerminal(event: RpcEvent, state: "done" | "error" | "cancelled") {
      if (this.handledTerminalRequests.has(event.request_id)) {
        return;
      }
      const result = markTerminalEvent(event);
      if (!result.accepted && result.error?.code === "rpc.event_out_of_order") {
        this.error = result.error;
        return;
      }
      if (!result.accepted) {
        return;
      }
      this.handledTerminalRequests.add(event.request_id);
      this.pendingRequests.delete(event.request_id);
      this.busy = this.pendingRequests.size > 0;

      if (state === "done") {
        this.messages.push({
          id: `msg_assistant_${Date.now().toString(36)}`,
          role: "assistant",
          content: this.streamingDraft || "收到。",
          request_id: event.request_id,
          trace_id: event.trace_id,
          status: "done"
        });
        this.streamingDraft = "";
        this.statusText = "回复完成";
      } else if (state === "cancelled") {
        this.statusText = "已停止";
        this.streamingDraft = "";
      } else {
        this.error = result.error ?? createRpcError("chat.error", "回复失败，可以重试或查看平台日志。", {}, true);
        this.statusText = "请求失败";
      }
    },
    dispose() {
      disposeLifecycle(this.lifecycle);
    },
    resetOnSidecarRestart() {
      restartLifecycle(this.lifecycle);
      for (const request of this.pendingRequests.values()) {
        this.messages.push({
          id: `msg_error_${request.request_id}`,
          role: "system",
          content: "sidecar 已重启，当前请求已停止。",
          request_id: request.request_id,
          trace_id: request.trace_id,
          status: "error"
        });
      }
      this.pendingRequests.clear();
      this.busy = false;
      this.streamingDraft = "";
      this.error = createRpcError("sidecar.restarted", "sidecar 已重启，当前聊天可重试。", {}, true);
      this.statusText = "sidecar 已重启";
    }
  }
});
