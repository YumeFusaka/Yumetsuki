import { ref } from 'vue'
import type { RpcErrorCode } from '../client/errorCodes'

export function useRpcTask() {
  const running = ref(false)
  const error = ref<RpcErrorCode | null>(null)

  async function run<T>(task: () => Promise<T>): Promise<T | null> {
    if (running.value) return null
    running.value = true
    error.value = null
    try {
      return await task()
    } catch {
      error.value = 'rpc.invalid_frame'
      return null
    } finally {
      running.value = false
    }
  }

  return { running, error, run }
}
