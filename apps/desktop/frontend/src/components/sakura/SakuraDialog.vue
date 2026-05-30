<script setup lang="ts">
defineProps<{ open?: boolean; title?: string; ariaLabel?: string }>()
defineEmits<{ close: [] }>()
</script>
<template>
  <div v-if="open" class="sakura-dialog" role="dialog" :aria-label="ariaLabel ?? title">
    <button type="button" @click="$emit('close')">关闭</button>
    <slot />
  </div>
</template>
