import { computed, ref } from "vue";
import type { RpcAccepted, RpcError } from "@/client/types/rpc";

export function useRpcTask() {
  const current = ref<RpcAccepted | null>(null);
  const error = ref<RpcError | null>(null);
  const running = computed(() => Boolean(current.value));

  function accept(task: RpcAccepted): void {
    current.value = task;
    error.value = null;
  }

  function fail(nextError: RpcError): void {
    error.value = nextError;
    current.value = null;
  }

  function clear(): void {
    current.value = null;
  }

  return { current, error, running, accept, fail, clear };
}
