<script setup lang="ts">
import { onBeforeUnmount, onMounted } from "vue";
import SakuraButton from "@/components/sakura/SakuraButton.vue";
import SakuraSettingsSection from "@/components/sakura/SakuraSettingsSection.vue";
import { useDiagnosticStore } from "@/stores/diagnosticStore";

const diagnosticStore = useDiagnosticStore();

onMounted(() => {
  void diagnosticStore.init();
});

onBeforeUnmount(() => {
  diagnosticStore.dispose();
});
</script>

<template>
  <section class="diagnostics-page" aria-labelledby="diagnostics-heading">
    <header>
      <h1 id="diagnostics-heading">诊断</h1>
      <p>运行状态与导出。</p>
    </header>

    <SakuraSettingsSection title="运行状态">
      <div class="diagnostics-page__status" role="status" aria-live="polite">
        <strong>{{ diagnosticStore.status }}</strong>
        <span>{{ diagnosticStore.summary || "等待运行" }}</span>
      </div>
      <progress :value="diagnosticStore.progress" max="100" aria-label="诊断进度"></progress>
      <div class="diagnostics-page__actions">
        <SakuraButton :busy="diagnosticStore.running" @click="diagnosticStore.run">运行诊断</SakuraButton>
        <SakuraButton :busy="diagnosticStore.exporting" :disabled="!diagnosticStore.reportHandle" @click="diagnosticStore.exportReport">
          导出报告
        </SakuraButton>
      </div>
      <p v-if="diagnosticStore.status === 'redaction-failed'" class="diagnostics-page__error">
        敏感扫描失败，已阻止导出。
      </p>
    </SakuraSettingsSection>
  </section>
</template>

<style scoped>
.diagnostics-page {
  display: grid;
  gap: var(--sakura-space-5);
}

h1 {
  margin: 0;
}

header p {
  color: var(--sakura-text-muted);
}

.diagnostics-page__status {
  display: flex;
  gap: var(--sakura-space-2);
  align-items: center;
}

.diagnostics-page__actions {
  display: flex;
  gap: var(--sakura-space-3);
  flex-wrap: wrap;
}

progress {
  width: min(420px, 100%);
  accent-color: var(--sakura-accent);
}

.diagnostics-page__error {
  color: var(--sakura-danger);
}
</style>
