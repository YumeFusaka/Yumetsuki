<script setup lang="ts">
defineProps<{ modelValue?: string; disabled?: boolean; ariaLabel?: string }>()
defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <input class="sakura-input" :value="modelValue" :disabled="disabled" :aria-label="ariaLabel" @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)" />
</template>
