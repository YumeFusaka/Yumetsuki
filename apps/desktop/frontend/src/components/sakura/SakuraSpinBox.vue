<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    id: string;
    label: string;
    modelValue: number;
    min?: number;
    max?: number;
    step?: number;
  }>(),
  {
    min: Number.NEGATIVE_INFINITY,
    max: Number.POSITIVE_INFINITY,
    step: 1
  }
);

const emit = defineEmits<{ "update:modelValue": [number] }>();

function clamp(value: number): number {
  return Math.min(props.max, Math.max(props.min, value));
}
</script>

<template>
  <label class="sakura-spinbox" :for="id">
    <span>{{ label }}</span>
    <span class="sakura-spinbox__row">
      <input
        :id="id"
        type="number"
        :value="modelValue"
        :min="Number.isFinite(min) ? min : undefined"
        :max="Number.isFinite(max) ? max : undefined"
        :step="step"
        @input="$emit('update:modelValue', clamp(Number(($event.target as HTMLInputElement).value)))"
      />
      <span class="sakura-spinbox__buttons" aria-hidden="false">
        <button type="button" aria-label="增加" @click="emit('update:modelValue', clamp(modelValue + step))">+</button>
        <button type="button" aria-label="减少" @click="emit('update:modelValue', clamp(modelValue - step))">-</button>
      </span>
    </span>
  </label>
</template>

<style scoped>
.sakura-spinbox {
  display: grid;
  gap: var(--sakura-space-1);
  color: var(--sakura-text-muted);
}

.sakura-spinbox__row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 34px;
  gap: var(--sakura-space-1);
}

input {
  min-height: 42px;
  border: 2px solid var(--sakura-border-strong);
  border-radius: var(--sakura-radius-md);
  padding: 0 var(--sakura-space-3);
  color: var(--sakura-text);
  background: rgba(255, 255, 255, 0.65);
}

.sakura-spinbox__buttons {
  display: grid;
  gap: 2px;
}

button {
  border: 0;
  border-radius: 5px;
  color: #fff;
  background: var(--sakura-accent);
  cursor: pointer;
}
</style>
