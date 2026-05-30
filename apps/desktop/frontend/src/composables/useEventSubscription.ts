import { onBeforeUnmount } from 'vue'

type UnlistenFn = () => void

export function useEventSubscription() {
  const unlistenFns: UnlistenFn[] = []

  function track(unlisten: UnlistenFn) {
    unlistenFns.push(unlisten)
  }

  function dispose() {
    for (const unlisten of unlistenFns.splice(0)) {
      unlisten()
    }
  }

  onBeforeUnmount(dispose)
  return { track, dispose }
}
