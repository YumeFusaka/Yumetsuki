<script setup lang="ts">
defineProps<{
  label: string;
  modelValue: string;
  options: Array<{ value: string; label: string; disabled?: boolean }>;
}>();

defineEmits<{ "update:modelValue": [string] }>();
</script>

<template>
  <fieldset class="sakura-radio-group">
    <legend>{{ label }}</legend>
    <label v-for="option in options" :key="option.value">
      <input
        type="radio"
        :checked="modelValue === option.value"
        :value="option.value"
        :disabled="option.disabled"
        @change="$emit('update:modelValue', option.value)"
      />
      <span>{{ option.label }}</span>
    </label>
  </fieldset>
</template>

<style scoped>
.sakura-radio-group {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sakura-space-2);
  margin: 0;
  padding: 0;
  border: 0;
}

legend {
  width: 100%;
  color: var(--sakura-text-muted);
  font-size: 0.9rem;
}

label {
  display: inline-flex;
  align-items: center;
  gap: var(--sakura-space-1);
  min-height: 34px;
  padding: 0 var(--sakura-space-3);
  border: 2px solid var(--sakura-border);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.56);
}
</style>
