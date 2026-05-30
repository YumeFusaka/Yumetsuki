import { describe, expect, it } from 'vitest'
import {
  createAppStore,
  createAudioStore,
  createCharacterStore,
  createChatStore,
  createConfigStore,
  createDiagnosticStore,
  createLogStore,
  createMcpStore,
  createPluginStore,
  createSttStore,
  createThemeStore,
  createToolStore,
  createWindowStore,
} from './index'

describe('store lifecycle', () => {
  it('keeps init idempotent and releaseable', () => {
    const stores = [
      createAppStore(),
      createWindowStore(),
      createThemeStore(),
      createConfigStore(),
      createChatStore(),
      createAudioStore(),
      createSttStore(),
      createLogStore(),
      createToolStore(),
      createPluginStore(),
      createMcpStore(),
      createDiagnosticStore(),
      createCharacterStore(),
    ]

    for (const store of stores) {
      expect(store.init()).toBeUndefined()
      expect(store.init()).toBeUndefined()
      expect(store.dispose()).toBeUndefined()
      expect(store.resetOnSidecarRestart()).toBeUndefined()
    }
  })

  it('marks chat terminal events only once', () => {
    const store = createChatStore()
    store.ingestTerminal('done')
    store.ingestTerminal('done')
    expect(store.terminalCount()).toBe(1)
  })
})
