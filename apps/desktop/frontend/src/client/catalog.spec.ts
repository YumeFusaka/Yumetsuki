import { describe, expect, it } from 'vitest'
import { RPC_EVENTS, RPC_METHODS, SCHEMA_HASH } from './types/rpc'

describe('RPC catalog projection', () => {
  it('pins the schema hash', () => {
    expect(SCHEMA_HASH).toMatch(/^[0-9a-f]{64}$/)
  })

  it('keeps security.confirm_required event-only', () => {
    expect(RPC_METHODS).not.toContain('security.confirm_required')
    expect(RPC_EVENTS).toContain('security.confirm_required')
  })

  it('keeps sidecar.cancel as the only cancel method', () => {
    expect(RPC_METHODS.filter((method) => method.includes('cancel'))).toEqual(['sidecar.cancel'])
  })
})
