<script setup lang="ts">
defineProps<{ modelValue?: boolean; ariaLabel?: string; disabled?: boolean }>()
defineEmits<{ 'update:modelValue': [value: boolean] }>()
</script>
<template>
  <button type="button" class="sakura-toggle" :aria-pressed="modelValue ? 'true' : 'false'" :aria-label="ariaLabel" :disabled="disabled" @click="$emit('update:modelValue', !modelValue)">
    <slot />
  </button>
</template>
