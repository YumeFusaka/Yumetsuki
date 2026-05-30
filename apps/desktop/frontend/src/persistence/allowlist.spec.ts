import { describe, expect, it } from 'vitest'
import { persistenceAllowlist, persistenceDeniedKeys } from './allowlist'

describe('persistence allowlist', () => {
  it('allows only the approved window fields', () => {
    expect(persistenceAllowlist.windowStore.allow).toEqual([
      'position',
      'size',
      'scale',
      'alwaysOnTop',
      'transparentPreference',
    ])
    expect(persistenceDeniedKeys.windowStore).toContain('request')
  })

  it('keeps chat draft out of persistence by default', () => {
    expect(persistenceAllowlist.chatStore.allow).not.toContain('inputDraft')
    expect(persistenceDeniedKeys.chatStore).toContain('inputDraft')
  })
})
