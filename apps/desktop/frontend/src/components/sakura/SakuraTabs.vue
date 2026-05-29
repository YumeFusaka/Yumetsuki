<script setup lang="ts">
defineProps<{
  label: string;
  modelValue: string;
  tabs: Array<{ value: string; label: string; disabled?: boolean }>;
}>();

defineEmits<{ "update:modelValue": [string] }>();
</script>

<template>
  <div class="sakura-tabs" role="tablist" :aria-label="label">
    <button
      v-for="tab in tabs"
      :key="tab.value"
      role="tab"
      type="button"
      :disabled="tab.disabled"
      :aria-selected="modelValue === tab.value"
      :tabindex="modelValue === tab.value ? 0 : -1"
      @click="$emit('update:modelValue', tab.value)"
    >
      {{ tab.label }}
    </button>
  </div>
</template>

<style scoped>
.sakura-tabs {
  display: flex;
  gap: var(--sakura-space-2);
  overflow-x: auto;
}

button {
  min-height: 36px;
  padding: 0 var(--sakura-space-3);
  border: 2px solid var(--sakura-border);
  border-radius: var(--sakura-radius-md);
  color: var(--sakura-text);
  background: rgba(255, 255, 255, 0.58);
  white-space: nowrap;
}

button[aria-selected="true"] {
  border-color: var(--sakura-accent-strong);
  background: #fff7f9;
}
</style>
