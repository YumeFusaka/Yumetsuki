<script setup lang="ts">
defineProps<{
  label?: string
  disabled?: boolean
  busy?: boolean
  danger?: boolean
  type?: 'button' | 'submit' | 'reset'
}>()
</script>

<template>
  <button
    class="sakura-button"
    :class="{ 'is-busy': busy, 'is-danger': danger }"
    :type="type ?? 'button'"
    :disabled="disabled || busy"
    :aria-disabled="disabled || busy ? 'true' : 'false'"
    :aria-busy="busy ? 'true' : 'false'"
  >
    <span class="sakura-button__label"><slot>{{ label }}</slot></span>
  </button>
</template>

<style scoped>
.sakura-button {
  min-height: 36px;
  padding: 0 16px;
  border: 1px solid var(--sakura-color-primary);
  border-radius: var(--sakura-radius-md);
  background: var(--sakura-color-primary);
  color: #fff;
  font: 600 14px/1 var(--sakura-font-family);
  transition: background var(--sakura-motion-fast), border-color var(--sakura-motion-fast);
}

.sakura-button:hover:not(:disabled) {
  background: var(--sakura-color-primary-strong);
}

.sakura-button:focus-visible {
  outline: 2px solid var(--sakura-color-accent);
  outline-offset: 2px;
}

.sakura-button:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.sakura-button.is-danger {
  border-color: var(--sakura-color-danger);
  background: var(--sakura-color-danger);
}
</style>
