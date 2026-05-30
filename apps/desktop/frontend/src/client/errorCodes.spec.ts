import { describe, expect, it } from 'vitest'
import { RPC_ERROR_CODES } from './errorCodes'

describe('RPC error codes', () => {
  it('includes canonical phase 1 error codes', () => {
    expect(RPC_ERROR_CODES).toContain('rpc.protocol_unsupported')
    expect(RPC_ERROR_CODES).toContain('rpc.method_not_found')
    expect(RPC_ERROR_CODES).toContain('sidecar.not_ready')
    expect(RPC_ERROR_CODES).toContain('filesystem.path_out_of_scope')
  })

  it('does not contain duplicate codes', () => {
    expect(new Set(RPC_ERROR_CODES).size).toBe(RPC_ERROR_CODES.length)
  })
})
