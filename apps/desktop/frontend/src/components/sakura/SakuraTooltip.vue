<script setup lang="ts">
defineProps<{
  text: string;
}>();
</script>

<template>
  <span class="sakura-tooltip">
    <slot />
    <span class="sakura-tooltip__bubble" role="tooltip">{{ text }}</span>
  </span>
</template>

<style scoped>
.sakura-tooltip {
  position: relative;
  display: inline-flex;
}

.sakura-tooltip__bubble {
  position: absolute;
  left: 50%;
  bottom: calc(100% + 8px);
  transform: translateX(-50%);
  width: max-content;
  max-width: min(260px, 90vw);
  padding: var(--sakura-space-2) var(--sakura-space-3);
  border: 1px solid var(--sakura-border);
  border-radius: var(--sakura-radius-sm);
  color: var(--sakura-text);
  background: var(--sakura-surface-solid);
  box-shadow: var(--sakura-shadow-sm);
  opacity: 0;
  pointer-events: none;
}

.sakura-tooltip:focus-within .sakura-tooltip__bubble,
.sakura-tooltip:hover .sakura-tooltip__bubble {
  opacity: 1;
}
</style>
