<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useLogStore } from "@/stores/logStore";

const logStore = useLogStore();
const listRef = ref<HTMLElement | null>(null);
const scrollTop = ref(0);
const viewportHeight = ref(0);
const rowHeight = 72;
const overscan = 8;

const filteredEntries = computed(() => logStore.filtered);
const startIndex = computed(() => Math.max(0, Math.floor(scrollTop.value / rowHeight) - overscan));
const visibleCount = computed(() => Math.ceil(viewportHeight.value / rowHeight) + overscan * 2);
const visibleRows = computed(() =>
  filteredEntries.value.slice(startIndex.value, startIndex.value + visibleCount.value).map((entry, index) => ({
    entry,
    absoluteIndex: startIndex.value + index
  }))
);
const totalHeight = computed(() => filteredEntries.value.length * rowHeight);
const topPadding = computed(() => startIndex.value * rowHeight);
const bottomPadding = computed(() =>
  Math.max(0, totalHeight.value - topPadding.value - visibleRows.value.length * rowHeight)
);

function updateViewport() {
  const element = listRef.value;
  if (!element) {
    return;
  }
  scrollTop.value = element.scrollTop;
  viewportHeight.value = element.clientHeight;
}

function onScroll() {
  updateViewport();
  const element = listRef.value;
  if (!element) {
    return;
  }
  const distanceToBottom = element.scrollHeight - element.scrollTop - element.clientHeight;
  logStore.followBottom = distanceToBottom < rowHeight * 2;
}

async function scrollToBottom() {
  await nextTick();
  const element = listRef.value;
  if (!element) {
    return;
  }
  element.scrollTop = element.scrollHeight;
  updateViewport();
}

onMounted(() => {
  void logStore.init();
  updateViewport();
  window.addEventListener("resize", updateViewport);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", updateViewport);
  logStore.dispose();
});

watch(
  () => filteredEntries.value.length,
  () => {
    if (logStore.followBottom && !logStore.selectionActive) {
      void scrollToBottom();
    }
  }
);
</script>

<template>
  <section class="virtual-log-list" data-testid="virtual-log-list" aria-label="平台日志列表">
    <header>
      <h2>平台日志</h2>
      <label>
        级别
        <select v-model="logStore.level" aria-label="日志级别筛选">
          <option value="all">全部</option>
          <option value="info">Info</option>
          <option value="warning">Warning</option>
          <option value="error">Error</option>
        </select>
      </label>
    </header>
    <div
      ref="listRef"
      class="virtual-log-list__items"
      role="list"
      :aria-setsize="filteredEntries.length"
      :style="{ '--top-padding': `${topPadding}px`, '--bottom-padding': `${bottomPadding}px` }"
      @scroll="onScroll"
      @mousedown="logStore.pauseForSelection(true)"
      @mouseup="logStore.pauseForSelection(false)"
      @mouseleave="logStore.pauseForSelection(false)"
    >
      <article
        v-for="{ entry, absoluteIndex } in visibleRows"
        :key="entry.id"
        role="listitem"
        class="log-entry"
        :aria-posinset="absoluteIndex + 1"
        :aria-setsize="filteredEntries.length"
      >
        <time>{{ new Date(entry.timestamp_ms).toLocaleTimeString() }}</time>
        <strong>{{ entry.level }}</strong>
        <span>{{ entry.source }}</span>
        <p>{{ entry.summary }}</p>
      </article>
      <p v-if="!filteredEntries.length" class="virtual-log-list__empty">暂无日志。</p>
    </div>
  </section>
</template>

<style scoped>
.virtual-log-list {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: var(--sakura-space-3);
  min-height: 300px;
}

header {
  display: flex;
  justify-content: space-between;
  gap: var(--sakura-space-3);
  align-items: center;
}

h2 {
  margin: 0;
  font-size: 1.1rem;
}

select {
  min-height: 34px;
  border: 2px solid var(--sakura-border);
  border-radius: var(--sakura-radius-sm);
  color: var(--sakura-text);
  background: rgba(255, 255, 255, 0.72);
}

.virtual-log-list__items {
  min-height: 0;
  overflow: auto;
  display: grid;
  align-content: start;
}

.virtual-log-list__items::before,
.virtual-log-list__items::after {
  content: "";
  display: block;
}

.virtual-log-list__items::before {
  height: var(--top-padding);
}

.virtual-log-list__items::after {
  height: var(--bottom-padding);
}

.log-entry {
  display: grid;
  grid-template-columns: 88px 70px 140px minmax(0, 1fr);
  gap: var(--sakura-space-2);
  height: 72px;
  box-sizing: border-box;
  padding: var(--sakura-space-2);
  border-bottom: 1px solid rgba(212, 86, 122, 0.22);
  overflow-wrap: anywhere;
  overflow: hidden;
  align-items: start;
}

.log-entry time,
.log-entry strong,
.log-entry span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-entry p {
  margin: 0;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.virtual-log-list__empty {
  color: var(--sakura-text-muted);
}

@media (max-width: 720px) {
  .log-entry {
    grid-template-columns: 74px 58px minmax(82px, 110px) minmax(0, 1fr);
    gap: var(--sakura-space-1);
  }
}
</style>
