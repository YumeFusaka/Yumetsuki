<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string;
    busy?: boolean;
    disabled?: boolean;
    danger?: boolean;
  }>(),
  {
    busy: false,
    disabled: false,
    danger: false
  }
);

defineEmits<{ click: [MouseEvent] }>();
</script>

<template>
  <button
    class="sakura-icon-button"
    :class="{ 'is-danger': danger }"
    type="button"
    :aria-label="label"
    :title="label"
    :aria-busy="busy"
    :disabled="disabled || busy"
    @click="$emit('click', $event)"
  >
    <slot />
  </button>
</template>

<style scoped>
.sakura-icon-button {
  width: 38px;
  height: 38px;
  display: inline-grid;
  place-items: center;
  border: 2px solid var(--sakura-border-strong);
  border-radius: 50%;
  color: var(--sakura-accent-strong);
  background: rgba(255, 255, 255, 0.68);
  cursor: pointer;
  transition:
    border-color var(--sakura-motion-fast),
    background var(--sakura-motion-fast);
}

.sakura-icon-button:hover:not(:disabled) {
  border-color: var(--sakura-accent-strong);
  background: #fff6f8;
}

.sakura-icon-button:disabled {
  cursor: not-allowed;
  opacity: 0.54;
}

.sakura-icon-button.is-danger {
  color: var(--sakura-danger);
}
</style>
