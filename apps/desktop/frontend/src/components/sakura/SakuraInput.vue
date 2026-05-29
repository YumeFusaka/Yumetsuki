<script setup lang="ts">
defineProps<{
  id: string;
  label: string;
  modelValue: string;
  placeholder?: string;
  disabled?: boolean;
  error?: string | null;
}>();

defineEmits<{ "update:modelValue": [string] }>();
</script>

<template>
  <label class="sakura-input" :for="id">
    <span class="sakura-input__label">{{ label }}</span>
    <input
      :id="id"
      class="sakura-input__control"
      :class="{ 'has-error': error }"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      :aria-invalid="Boolean(error)"
      :aria-describedby="error ? `${id}-error` : undefined"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
    <span v-if="error" :id="`${id}-error`" class="sakura-input__error">{{ error }}</span>
  </label>
</template>

<style scoped>
.sakura-input {
  display: grid;
  gap: var(--sakura-space-1);
  color: var(--sakura-text);
}

.sakura-input__label {
  font-size: 0.9rem;
  color: var(--sakura-text-muted);
}

.sakura-input__control {
  min-height: 38px;
  width: 100%;
  border: 2px solid var(--sakura-border-strong);
  border-radius: var(--sakura-radius-md);
  padding: 0 var(--sakura-space-3);
  color: var(--sakura-text);
  background: rgba(255, 255, 255, 0.62);
}

.sakura-input__control:focus {
  border-color: var(--sakura-accent-strong);
}

.sakura-input__control.has-error {
  border-color: var(--sakura-danger);
}

.sakura-input__error {
  color: var(--sakura-danger);
  font-size: 0.84rem;
}
</style>
