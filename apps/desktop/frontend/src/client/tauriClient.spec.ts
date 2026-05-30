import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(),
}))

vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn(),
}))

describe('tauri client', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
  })

  it('injects request and trace ids for commands', async () => {
    const { createTauriClient } = await import('./tauriClient')
    const client = createTauriClient({ requestId: () => 'req-1', traceId: () => 'trace-1' })

    await client.commands.call('chat.send', { text: 'hello' })

    const { invoke } = await import('@tauri-apps/api/core')
    expect(invoke).toHaveBeenCalledWith('chat.send', expect.objectContaining({
      request_id: 'req-1',
      trace_id: 'trace-1',
    }))
  })

  it('drops late terminal updates after timeout', async () => {
    const { createRpcTaskTracker } = await import('./tauriClient')
    const tracker = createRpcTaskTracker()
    const task = tracker.open('req-1', 5)

    task.timeout()
    task.terminal({ kind: 'done' })

    expect(task.state()).toBe('error')
  })

  it('ignores duplicate terminal events', async () => {
    const { createRpcTaskTracker } = await import('./tauriClient')
    const tracker = createRpcTaskTracker()
    const task = tracker.open('req-1', 5)

    task.terminal({ kind: 'done', payload: 1 })
    task.terminal({ kind: 'done', payload: 2 })

    expect(task.terminalCount()).toBe(1)
  })

  it('marks out of order delta events', async () => {
    const { createRpcTaskTracker } = await import('./tauriClient')
    const tracker = createRpcTaskTracker()
    const task = tracker.open('req-1', 5)

    task.delta({ seq: 2 })

    expect(task.errors()).toContain('rpc.event_out_of_order')
  })

  it('stops updating after unsubscribe', async () => {
    const { createSubscriptionStore } = await import('./tauriClient')
    const store = createSubscriptionStore()
    const stop = vi.fn()
    const handle = store.track('chat.delta', stop)

    handle.unsubscribe()
    handle.publish({ text: 'late' })

    expect(stop).toHaveBeenCalledTimes(1)
    expect(store.snapshot()).toEqual([])
  })
})
