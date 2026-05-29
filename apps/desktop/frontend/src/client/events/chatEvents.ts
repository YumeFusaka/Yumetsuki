import { subscribeEvent } from "../tauriClient";
import type { ChatDeltaPayload, RpcError, RpcEvent, UnlistenFn } from "../types/rpc";

export function onChatDelta(handler: (event: RpcEvent<ChatDeltaPayload>) => void): Promise<UnlistenFn> {
  return subscribeEvent("chat.delta", handler);
}

export function onChatDone(handler: (event: RpcEvent<{ message_id: string }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("chat.done", handler);
}

export function onChatError(handler: (event: RpcEvent<{ error: RpcError }>) => void): Promise<UnlistenFn> {
  return subscribeEvent("chat.error", handler);
}

export function onChatCancelled(handler: (event: RpcEvent<Record<string, never>>) => void): Promise<UnlistenFn> {
  return subscribeEvent("chat.cancelled", handler);
}
