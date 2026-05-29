<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import SakuraButton from "@/components/sakura/SakuraButton.vue";
import SakuraSelect from "@/components/sakura/SakuraSelect.vue";
import SakuraSettingsSection from "@/components/sakura/SakuraSettingsSection.vue";
import SakuraSpinBox from "@/components/sakura/SakuraSpinBox.vue";
import SakuraToast from "@/components/sakura/SakuraToast.vue";
import { useConfigStore } from "@/stores/configStore";

const configStore = useConfigStore();
const showToast = ref(false);

onMounted(() => {
  void configStore.init();
});

onBeforeUnmount(() => {
  configStore.dispose();
});

async function markSaved() {
  await configStore.saveSystem();
  if (!configStore.error) {
    showToast.value = true;
    window.setTimeout(() => {
      showToast.value = false;
    }, 1600);
  }
}
</script>

<template>
  <section class="settings-page" aria-labelledby="settings-heading">
    <header>
      <h1 id="settings-heading">设置中心</h1>
      <p>系统设置</p>
    </header>

    <div class="settings-page__content">
      <SakuraSettingsSection title="基础外观">
        <SakuraSelect
          id="theme"
          v-model="configStore.draft.system.theme"
          label="主题"
          :options="[{ value: 'sakura', label: 'Sakura' }]"
        />
        <SakuraSpinBox
          id="font-scale"
          :model-value="configStore.draft.system.font_scale"
          label="聊天字体倍率"
          :min="0.8"
          :max="2"
          :step="0.1"
          @update:model-value="configStore.editDraft($event)"
        />
      </SakuraSettingsSection>

      <footer>
        <SakuraButton :busy="configStore.saving" :disabled="!configStore.dirty" @click="markSaved">保存系统配置</SakuraButton>
      </footer>
    </div>

    <SakuraToast v-if="showToast" message="系统设置已保存。" tone="success" />
  </section>
</template>

<style scoped>
.settings-page {
  display: grid;
  gap: var(--sakura-space-5);
}

h1 {
  margin: 0;
}

header p {
  color: var(--sakura-text-muted);
}

.settings-page__content {
  min-width: 0;
}

footer {
  margin-top: var(--sakura-space-4);
}

@media (max-width: 720px) {}
</style>
