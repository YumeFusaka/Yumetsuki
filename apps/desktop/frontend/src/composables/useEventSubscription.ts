import { onBeforeUnmount, ref } from "vue";
import type { UnlistenFn } from "@/client/types/rpc";

export function useEventSubscription() {
  const subscriptions = ref<UnlistenFn[]>([]);

  function add(unlisten: UnlistenFn): void {
    subscriptions.value.push(unlisten);
  }

  function dispose(): void {
    for (const unsubscribe of subscriptions.value.splice(0)) {
      unsubscribe();
    }
  }

  onBeforeUnmount(dispose);

  return { add, dispose, subscriptions };
}
