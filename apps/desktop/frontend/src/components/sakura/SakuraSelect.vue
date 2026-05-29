<script setup lang="ts">
defineProps<{
  id: string;
  label: string;
  modelValue: string;
  options: Array<{ value: string; label: string; disabled?: boolean }>;
  disabled?: boolean;
}>();

defineEmits<{ "update:modelValue": [string] }>();
</script>

<template>
  <label class="sakura-select" :for="id">
    <span>{{ label }}</span>
    <select
      :id="id"
      :value="modelValue"
      :disabled="disabled"
      @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
    >
      <option v-for="option in options" :key="option.value" :value="option.value" :disabled="option.disabled">
        {{ option.label }}
      </option>
    </select>
  </label>
</template>

<style scoped>
.sakura-select {
  display: grid;
  gap: var(--sakura-space-1);
  color: var(--sakura-text-muted);
}

select {
  min-height: 38px;
  border: 2px solid var(--sakura-border-strong);
  border-radius: var(--sakura-radius-md);
  padding: 0 var(--sakura-space-3);
  color: var(--sakura-text);
  background: rgba(255, 255, 255, 0.68);
}
</style>
