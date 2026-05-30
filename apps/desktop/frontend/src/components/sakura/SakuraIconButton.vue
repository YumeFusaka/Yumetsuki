<script setup lang="ts">
defineProps<{ ariaLabel: string; disabled?: boolean; busy?: boolean; danger?: boolean }>()
</script>

<template>
  <button
    class="sakura-icon-button"
    type="button"
    :aria-label="ariaLabel"
    :disabled="disabled || busy"
    :aria-busy="busy ? 'true' : 'false'"
  >
    <slot />
  </button>
</template>
