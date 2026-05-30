<script setup lang="ts">
defineProps<{ modelValue?: string; tabs?: string[]; ariaLabel?: string }>()
defineEmits<{ 'update:modelValue': [value: string] }>()
</script>
<template>
  <div class="sakura-tabs" role="tablist" :aria-label="ariaLabel">
    <button v-for="tab in tabs ?? []" :key="tab" type="button" role="tab" :aria-selected="modelValue === tab" @click="$emit('update:modelValue', tab)">{{ tab }}</button>
  </div>
</template>
