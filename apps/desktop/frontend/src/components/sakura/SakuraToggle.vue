<script setup lang="ts">
defineProps<{
  label: string;
  modelValue: boolean;
  disabled?: boolean;
}>();

defineEmits<{ "update:modelValue": [boolean] }>();
</script>

<template>
  <label class="sakura-toggle">
    <input
      type="checkbox"
      :checked="modelValue"
      :disabled="disabled"
      @change="$emit('update:modelValue', ($event.target as HTMLInputElement).checked)"
    />
    <span aria-hidden="true"></span>
    <strong>{{ label }}</strong>
  </label>
</template>

<style scoped>
.sakura-toggle {
  display: inline-flex;
  align-items: center;
  gap: var(--sakura-space-2);
  cursor: pointer;
}

input {
  position: absolute;
  opacity: 0;
}

span {
  width: 42px;
  height: 24px;
  border: 2px solid var(--sakura-border-strong);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.65);
  position: relative;
}

span::after {
  content: "";
  position: absolute;
  top: 3px;
  left: 3px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--sakura-accent);
  transition: transform var(--sakura-motion-fast);
}

input:checked + span::after {
  transform: translateX(18px);
}

input:focus-visible + span {
  outline: 3px solid var(--sakura-focus);
  outline-offset: 2px;
}
</style>
