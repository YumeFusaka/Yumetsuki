<script setup lang="ts">
import VirtualLogList from "@/components/VirtualLogList.vue";
</script>

<template>
  <section class="logs-page" aria-labelledby="logs-heading">
    <header>
      <h1 id="logs-heading">日志工作台</h1>
      <p>结构化日志与筛选。</p>
    </header>
    <VirtualLogList />
  </section>
</template>

<style scoped>
.logs-page {
  display: grid;
  gap: var(--sakura-space-5);
  min-height: 100%;
}

h1 {
  margin: 0;
}

p {
  color: var(--sakura-text-muted);
}
</style>
