<script setup lang="ts">
withDefaults(
  defineProps<{
    id: string;
    label: string;
    modelValue: number;
    min?: number;
    max?: number;
    step?: number;
  }>(),
  {
    min: 0,
    max: 100,
    step: 1
  }
);

defineEmits<{ "update:modelValue": [number] }>();
</script>

<template>
  <label class="sakura-slider" :for="id">
    <span>{{ label }}：{{ modelValue }}</span>
    <input
      :id="id"
      type="range"
      :value="modelValue"
      :min="min"
      :max="max"
      :step="step"
      @input="$emit('update:modelValue', Number(($event.target as HTMLInputElement).value))"
    />
  </label>
</template>

<style scoped>
.sakura-slider {
  display: grid;
  gap: var(--sakura-space-2);
  color: var(--sakura-text-muted);
}

input {
  accent-color: var(--sakura-accent);
}
</style>
