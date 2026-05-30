import { ref } from 'vue'

export function useConfirmDialog() {
  const open = ref(false)
  const message = ref('')

  function requestConfirm(nextMessage: string) {
    message.value = nextMessage
    open.value = true
  }

  function close() {
    open.value = false
  }

  return { open, message, requestConfirm, close }
}
