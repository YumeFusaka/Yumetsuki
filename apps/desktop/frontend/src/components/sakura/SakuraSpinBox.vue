<script setup lang="ts">
defineProps<{ modelValue?: number; disabled?: boolean; ariaLabel?: string }>()
defineEmits<{ 'update:modelValue': [value: number] }>()
</script>
<template>
  <input class="sakura-spinbox" type="number" :value="modelValue" :disabled="disabled" :aria-label="ariaLabel" @input="$emit('update:modelValue', Number(($event.target as HTMLInputElement).value))" />
</template>
