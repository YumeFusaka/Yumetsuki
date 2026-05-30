<script setup lang="ts">
defineProps<{ modelValue?: string; options?: string[]; ariaLabel?: string }>()
defineEmits<{ 'update:modelValue': [value: string] }>()
</script>
<template>
  <div class="sakura-radio-group" role="radiogroup" :aria-label="ariaLabel">
    <label v-for="option in options ?? []" :key="option">
      <input type="radio" :checked="modelValue === option" @change="$emit('update:modelValue', option)" />
      {{ option }}
    </label>
  </div>
</template>
