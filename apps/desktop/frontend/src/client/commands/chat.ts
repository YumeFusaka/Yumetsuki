import { invokeCommand } from "../tauriClient";
import type { CommandOptions, RpcAccepted } from "../types/rpc";

export interface SendChatParams {
  message?: string;
  text?: string;
  session_id?: string;
}

export function sendChat(params: SendChatParams, options: CommandOptions = {}): Promise<RpcAccepted> {
  const text = params.text ?? params.message ?? "";
  const session_id = params.session_id ?? options.session_id ?? "default-session";
  return invokeCommand<RpcAccepted, SendChatParams>("chat.send", { ...params, text }, {
    ...options,
    session_id
  });
}

export function retryChat(request_id: string, options?: CommandOptions): Promise<RpcAccepted> {
  return invokeCommand<RpcAccepted>("chat.retry", { request_id }, options);
}
