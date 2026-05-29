import { ref } from "vue";

export function useConfirmDialog() {
  const open = ref(false);
  const title = ref("");
  const message = ref("");
  let resolver: ((confirmed: boolean) => void) | null = null;

  function confirm(nextTitle: string, nextMessage: string): Promise<boolean> {
    title.value = nextTitle;
    message.value = nextMessage;
    open.value = true;
    return new Promise<boolean>((resolve) => {
      resolver = resolve;
    });
  }

  function close(confirmed: boolean): void {
    open.value = false;
    resolver?.(confirmed);
    resolver = null;
  }

  return { open, title, message, confirm, close };
}
