<script setup lang="ts">
defineProps<{ modelValue?: string; options?: string[]; ariaLabel?: string }>()
defineEmits<{ 'update:modelValue': [value: string] }>()
</script>
<template>
  <div class="sakura-segmented-control" role="tablist" :aria-label="ariaLabel">
    <button v-for="option in options ?? []" :key="option" type="button" role="tab" :aria-selected="modelValue === option" @click="$emit('update:modelValue', option)">{{ option }}</button>
  </div>
</template>
