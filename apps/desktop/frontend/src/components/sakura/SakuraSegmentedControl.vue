<script setup lang="ts">
defineProps<{
  label: string;
  modelValue: string;
  options: Array<{ value: string; label: string; disabled?: boolean }>;
}>();

defineEmits<{ "update:modelValue": [string] }>();
</script>

<template>
  <div class="sakura-segmented" role="group" :aria-label="label">
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      :disabled="option.disabled"
      :aria-pressed="modelValue === option.value"
      :class="{ selected: modelValue === option.value }"
      @click="$emit('update:modelValue', option.value)"
    >
      {{ option.label }}
    </button>
  </div>
</template>

<style scoped>
.sakura-segmented {
  display: inline-flex;
  padding: 3px;
  border: 2px solid var(--sakura-border);
  border-radius: var(--sakura-radius-md);
  background: rgba(255, 255, 255, 0.5);
}

button {
  min-height: 32px;
  padding: 0 var(--sakura-space-3);
  border: 0;
  border-radius: 6px;
  color: var(--sakura-text);
  background: transparent;
  cursor: pointer;
}

button.selected {
  color: #fff;
  background: var(--sakura-accent);
}
</style>
