<script setup lang="ts">
defineProps<{
  logs?: string[]
}>()
</script>

<template>
  <section class="virtual-log-list" aria-label="日志列表" data-testid="log-list">
    <div class="virtual-log-list__toolbar">
      <span>日志</span>
      <button type="button" disabled>跟随底部</button>
    </div>
    <ol>
      <li v-for="(log, index) in logs ?? ['sidecar hello ok', 'schema hash ready']" :key="`${index}-${log}`">
        {{ log }}
      </li>
    </ol>
  </section>
</template>

<style scoped>
.virtual-log-list {
  min-height: 160px;
  overflow: auto;
  border: 1px solid var(--sakura-color-border);
  border-radius: var(--sakura-radius-md);
  background: var(--sakura-color-surface);
}

.virtual-log-list__toolbar {
  position: sticky;
  top: 0;
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: #fff;
  border-bottom: 1px solid var(--sakura-color-border);
}

.virtual-log-list ol {
  margin: 0;
  padding: 12px 32px;
}
</style>
