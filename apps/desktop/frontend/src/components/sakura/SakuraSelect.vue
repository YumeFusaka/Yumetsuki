<script setup lang="ts">
defineProps<{ modelValue?: string; options?: string[]; ariaLabel?: string; disabled?: boolean }>()
defineEmits<{ 'update:modelValue': [value: string] }>()
</script>
<template>
  <select class="sakura-select" :value="modelValue" :disabled="disabled" :aria-label="ariaLabel" @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value)">
    <option v-for="option in options ?? []" :key="option" :value="option">{{ option }}</option>
  </select>
</template>
