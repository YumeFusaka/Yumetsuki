<script setup lang="ts">
defineProps<{ modelValue?: number; min?: number; max?: number; disabled?: boolean; ariaLabel?: string }>()
defineEmits<{ 'update:modelValue': [value: number] }>()
</script>
<template>
  <input class="sakura-slider" type="range" :value="modelValue" :min="min" :max="max" :disabled="disabled" :aria-label="ariaLabel" @input="$emit('update:modelValue', Number(($event.target as HTMLInputElement).value))" />
</template>
