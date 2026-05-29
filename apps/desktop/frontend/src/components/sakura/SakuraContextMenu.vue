<script setup lang="ts">
defineProps<{
  label: string;
  items: Array<{ id: string; label: string; disabled?: boolean; danger?: boolean }>;
}>();

defineEmits<{ select: [string] }>();
</script>

<template>
  <div class="sakura-context-menu" role="menu" :aria-label="label">
    <button
      v-for="item in items"
      :key="item.id"
      role="menuitem"
      type="button"
      :disabled="item.disabled"
      :class="{ danger: item.danger }"
      @click="$emit('select', item.id)"
    >
      {{ item.label }}
    </button>
  </div>
</template>

<style scoped>
.sakura-context-menu {
  min-width: 180px;
  padding: var(--sakura-space-1);
  border: 1px solid var(--sakura-border);
  border-radius: var(--sakura-radius-md);
  background: var(--sakura-surface-solid);
  box-shadow: var(--sakura-shadow-sm);
}

button {
  width: 100%;
  min-height: 34px;
  border: 0;
  border-radius: var(--sakura-radius-sm);
  color: var(--sakura-text);
  text-align: left;
  background: transparent;
}

button:hover:not(:disabled),
button:focus-visible {
  background: #fff0f4;
}

button.danger {
  color: var(--sakura-danger);
}
</style>
