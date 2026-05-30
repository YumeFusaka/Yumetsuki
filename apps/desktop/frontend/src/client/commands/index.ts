import { createTauriClient } from '../tauriClient'

const client = createTauriClient()

export function sidecarHello() {
  return client.commands.call('sidecar.hello', {})
}

export function sidecarHealth() {
  return client.commands.call('sidecar.health', {})
}

export async function chatSend(text: string) {
  const request = await client.commands.call<{ request_id?: string }, { text: string }>('chat.send', { text })
  return {
    accepted: true as const,
    requestId: request.request_id ?? '',
    taskType: 'chat.send' as const,
  }
}

export function cancelSidecarTask(requestId: string) {
  return client.commands.call('sidecar.cancel', { request_id: requestId })
}
