import { invoke } from '@tauri-apps/api/core'
import { listen, type UnlistenFn } from '@tauri-apps/api/event'
import type { RpcErrorCode } from './errorCodes'
import type { RpcEvent, RpcMethod } from './types/rpc'

type IdFactory = () => string

export interface TauriClientOptions {
  requestId?: IdFactory
  traceId?: IdFactory
}

export interface CommandEnvelope<TParams extends Record<string, unknown>> extends TParams {
  request_id: string
  trace_id: string
  parent_trace_id?: string
}

function randomId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`
}

export function createTauriClient(options: TauriClientOptions = {}) {
  const requestId = options.requestId ?? (() => randomId('req'))
  const traceId = options.traceId ?? (() => randomId('trace'))

  return {
    commands: {
      call<TResult = unknown, TParams extends Record<string, unknown> = Record<string, unknown>>(
        method: RpcMethod,
        params: TParams,
        parentTraceId?: string,
      ): Promise<TResult> {
        const envelope: CommandEnvelope<TParams> = {
          ...params,
          request_id: requestId(),
          trace_id: traceId(),
        }
        if (parentTraceId) {
          envelope.parent_trace_id = parentTraceId
        }
        return invoke<TResult>(method, envelope)
      },
    },
    events: {
      subscribe<TPayload>(event: RpcEvent, handler: (payload: TPayload) => void): Promise<UnlistenFn> {
        return listen<TPayload>(event, (message) => handler(message.payload))
      },
    },
  }
}

export type TaskState = 'pending' | 'streaming' | 'done' | 'error'

interface TerminalEvent {
  kind: 'done' | 'error' | 'cancelled'
  payload?: unknown
}

interface DeltaEvent {
  seq: number
}

export function createRpcTaskTracker() {
  const tasks = new Map<string, ReturnType<typeof createTask>>()

  return {
    open(requestId: string, timeoutMs: number) {
      const task = createTask(timeoutMs)
      tasks.set(requestId, task)
      return task
    },
    get(requestId: string) {
      return tasks.get(requestId)
    },
  }
}

function createTask(_timeoutMs: number) {
  let state: TaskState = 'pending'
  let terminalSeen = false
  let terminalEvents = 0
  let expectedSeq = 1
  const errors: RpcErrorCode[] = []

  return {
    timeout() {
      if (terminalSeen) return
      terminalSeen = true
      terminalEvents += 1
      state = 'error'
      errors.push('rpc.request_timeout')
    },
    terminal(_event: TerminalEvent) {
      if (terminalSeen) return
      terminalSeen = true
      terminalEvents += 1
      state = _event.kind === 'done' ? 'done' : 'error'
    },
    delta(event: DeltaEvent) {
      if (terminalSeen) return
      if (event.seq !== expectedSeq) {
        errors.push('rpc.event_out_of_order')
        return
      }
      expectedSeq += 1
      state = 'streaming'
    },
    state() {
      return state
    },
    terminalCount() {
      return terminalEvents
    },
    errors() {
      return [...errors]
    },
  }
}

export function createSubscriptionStore() {
  const events: unknown[] = []

  return {
    track(_event: RpcEvent, unlisten: UnlistenFn) {
      let active = true
      return {
        unsubscribe() {
          if (!active) return
          active = false
          unlisten()
        },
        publish(payload: unknown) {
          if (active) {
            events.push(payload)
          }
        },
      }
    },
    snapshot() {
      return [...events]
    },
  }
}
