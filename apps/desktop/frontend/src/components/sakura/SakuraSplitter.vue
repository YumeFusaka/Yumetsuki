<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string;
    asideWidth?: string;
  }>(),
  {
    asideWidth: "320px"
  }
);
</script>

<template>
  <div class="sakura-splitter" :aria-label="label">
    <aside :style="{ '--aside-width': asideWidth }">
      <slot name="aside" />
    </aside>
    <div class="sakura-splitter__main">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.sakura-splitter {
  display: grid;
  grid-template-columns: minmax(220px, var(--aside-width)) minmax(0, 1fr);
  gap: var(--sakura-space-4);
  min-height: 0;
}

aside,
.sakura-splitter__main {
  min-width: 0;
  min-height: 0;
}

@media (max-width: 760px) {
  .sakura-splitter {
    grid-template-columns: 1fr;
  }
}
</style>
