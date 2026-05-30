export interface LifecycleStore {
  readonly name: string
  init(): void
  dispose(): void
  resetOnSidecarRestart(): void
}

export function createLifecycleStore(name: string, onRestart?: () => void): LifecycleStore {
  let initialized = false
  let unlisten: Array<() => void> = []

  return {
    name,
    init() {
      if (initialized) return
      initialized = true
      unlisten = [() => undefined]
    },
    dispose() {
      for (const stop of unlisten.splice(0)) {
        stop()
      }
      initialized = false
    },
    resetOnSidecarRestart() {
      this.dispose()
      onRestart?.()
    },
  }
}
