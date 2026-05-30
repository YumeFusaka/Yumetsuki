import { createLifecycleStore, type LifecycleStore } from './base'

export function createAppStore(): LifecycleStore & { sidecarStatus: string } {
  const state = { sidecarStatus: 'ready' }
  return {
    ...createLifecycleStore('appStore', () => {
      state.sidecarStatus = 'degraded'
    }),
    get sidecarStatus() {
      return state.sidecarStatus
    },
  }
}

export function createWindowStore() {
  return createLifecycleStore('windowStore')
}

export function createThemeStore() {
  return createLifecycleStore('themeStore')
}

export function createConfigStore() {
  return createLifecycleStore('configStore')
}

export function createAudioStore() {
  return createLifecycleStore('audioStore')
}

export function createSttStore() {
  return createLifecycleStore('sttStore')
}

export function createLogStore() {
  return createLifecycleStore('logStore')
}

export function createToolStore() {
  return createLifecycleStore('toolStore')
}

export function createPluginStore() {
  return createLifecycleStore('pluginStore')
}

export function createMcpStore() {
  return createLifecycleStore('mcpStore')
}

export function createDiagnosticStore() {
  return createLifecycleStore('diagnosticStore')
}

export function createCharacterStore() {
  return createLifecycleStore('characterStore')
}

export function createChatStore() {
  const base = createLifecycleStore('chatStore')
  let terminalSeen = false
  let terminalEvents = 0

  return {
    ...base,
    ingestTerminal(_kind: 'done' | 'error' | 'cancelled') {
      if (terminalSeen) return
      terminalSeen = true
      terminalEvents += 1
    },
    terminalCount() {
      return terminalEvents
    },
    resetOnSidecarRestart() {
      base.resetOnSidecarRestart()
      terminalSeen = false
      terminalEvents = 0
    },
  }
}
