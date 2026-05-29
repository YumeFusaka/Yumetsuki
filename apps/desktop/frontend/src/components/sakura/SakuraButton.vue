<script setup lang="ts">
withDefaults(
  defineProps<{
    type?: "button" | "submit" | "reset";
    busy?: boolean;
    danger?: boolean;
    disabled?: boolean;
    ariaLabel?: string;
  }>(),
  {
    type: "button",
    busy: false,
    danger: false,
    disabled: false,
    ariaLabel: undefined
  }
);

defineEmits<{ click: [MouseEvent] }>();
</script>

<template>
  <button
    class="sakura-button"
    :class="{ 'is-danger': danger, 'is-busy': busy }"
    :type="type"
    :disabled="disabled || busy"
    :aria-busy="busy"
    :aria-label="ariaLabel"
    @click="$emit('click', $event)"
  >
    <span class="sakura-button__content"><slot /></span>
  </button>
</template>

<style scoped>
.sakura-button {
  min-height: 36px;
  padding: 0 var(--sakura-space-4);
  border: 2px solid var(--sakura-border-strong);
  border-radius: var(--sakura-radius-md);
  color: var(--sakura-text);
  background: rgba(255, 255, 255, 0.62);
  box-shadow: var(--sakura-shadow-sm);
  cursor: pointer;
  transition:
    border-color var(--sakura-motion-fast),
    background var(--sakura-motion-fast),
    transform var(--sakura-motion-fast);
}

.sakura-button:hover:not(:disabled) {
  border-color: var(--sakura-accent-strong);
  background: #fff6f8;
  transform: translateY(-1px);
}

.sakura-button:disabled {
  cursor: not-allowed;
  opacity: 0.56;
}

.sakura-button.is-danger {
  border-color: var(--sakura-danger);
  color: #7b1f32;
}

.sakura-button.is-busy .sakura-button__content {
  opacity: 0.72;
}
</style>
