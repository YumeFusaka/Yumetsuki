<script setup lang="ts">
defineProps<{
  message: string;
  tone?: "info" | "success" | "error";
}>();
</script>

<template>
  <div class="sakura-toast" :class="tone ?? 'info'" role="status" aria-live="polite">
    {{ message }}
  </div>
</template>

<style scoped>
.sakura-toast {
  max-width: min(520px, calc(100vw - 32px));
  padding: var(--sakura-space-3) var(--sakura-space-4);
  border: 2px solid var(--sakura-border-strong);
  border-radius: var(--sakura-radius-md);
  background: var(--sakura-surface-solid);
  box-shadow: var(--sakura-shadow-md);
}

.sakura-toast.error {
  border-color: var(--sakura-danger);
}

.sakura-toast.success {
  border-color: var(--sakura-success);
}
</style>
