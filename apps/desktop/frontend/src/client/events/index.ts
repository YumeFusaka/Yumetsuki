import type { UnlistenFn } from '@tauri-apps/api/event'
import { createTauriClient } from '../tauriClient'
import type { RpcEvent } from '../types/rpc'

const client = createTauriClient()

export function subscribeRpcEvent<TPayload>(
  event: RpcEvent,
  handler: (payload: TPayload) => void,
): Promise<UnlistenFn> {
  return client.events.subscribe(event, handler)
}

export function subscribeChatDelta(handler: (payload: unknown) => void): Promise<UnlistenFn> {
  return subscribeRpcEvent('chat.delta', handler)
}
