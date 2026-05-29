<script setup lang="ts">
import { onBeforeUnmount, onMounted } from "vue";
import SakuraButton from "@/components/sakura/SakuraButton.vue";
import SakuraInput from "@/components/sakura/SakuraInput.vue";
import SakuraSegmentedControl from "@/components/sakura/SakuraSegmentedControl.vue";
import SakuraSettingsSection from "@/components/sakura/SakuraSettingsSection.vue";
import { useMcpStore } from "@/stores/mcpStore";
import { usePluginStore } from "@/stores/pluginStore";
import { useToolStore } from "@/stores/toolStore";

const toolStore = useToolStore();
const pluginStore = usePluginStore();
const mcpStore = useMcpStore();

const toolFilterOptions = [
  { value: "all", label: "全部" },
  { value: "enabled", label: "启用" },
  { value: "disabled", label: "禁用" },
  { value: "confirmation", label: "需确认" }
];

const pluginFilterOptions = [
  { value: "all", label: "全部" },
  { value: "enabled", label: "启用" },
  { value: "disabled", label: "禁用" },
  { value: "loaded", label: "已加载" }
];

const mcpFilterOptions = [
  { value: "all", label: "全部" },
  { value: "enabled", label: "启用" },
  { value: "disabled", label: "禁用" },
  { value: "ready", label: "Ready" }
];

onMounted(() => {
  void Promise.all([toolStore.init(), pluginStore.init(), mcpStore.init()]);
});

onBeforeUnmount(() => {
  toolStore.dispose();
  pluginStore.dispose();
  mcpStore.dispose();
});
</script>

<template>
  <section class="tools-page" aria-labelledby="tools-heading">
    <header class="tools-page__header">
      <div>
        <h1 id="tools-heading">工具与集成</h1>
        <p>Tauri command bridge 已连接工具、插件、MCP 和安全授权摘要。</p>
      </div>
      <dl class="tools-page__summary" aria-label="集成摘要">
        <div>
          <dt>工具</dt>
          <dd>{{ toolStore.items.length }}</dd>
        </div>
        <div>
          <dt>插件</dt>
          <dd>{{ pluginStore.items.length }}</dd>
        </div>
        <div>
          <dt>MCP</dt>
          <dd>{{ mcpStore.servers.length }}</dd>
        </div>
        <div>
          <dt>授权</dt>
          <dd>{{ toolStore.grantCount }}</dd>
        </div>
      </dl>
    </header>

    <div class="tools-page__grid">
      <SakuraSettingsSection title="工具">
        <div class="tools-page__toolbar">
          <SakuraSegmentedControl v-model="toolStore.filter" label="工具筛选" :options="toolFilterOptions" />
          <SakuraButton :busy="toolStore.status === 'loading'" @click="toolStore.reload()">刷新</SakuraButton>
        </div>

        <p class="tools-page__status" role="status" aria-live="polite">
          {{ toolStore.lastResult || `状态：${toolStore.status}` }}
        </p>
        <p v-if="toolStore.error" class="tools-page__error">{{ toolStore.error.user_message }}</p>

        <div class="tools-page__rows" role="list" aria-label="工具列表">
          <article v-for="tool in toolStore.filteredItems" :key="tool.tool_name" class="tools-page__row" role="listitem">
            <div class="tools-page__row-main">
              <strong>{{ tool.tool_name }}</strong>
              <span>{{ tool.description || "sidecar 工具" }}</span>
            </div>
            <div class="tools-page__badges">
              <span :class="{ muted: !tool.enabled }">{{ tool.enabled ? "启用" : "禁用" }}</span>
              <span v-if="tool.requires_confirmation">需确认</span>
            </div>
            <SakuraButton :disabled="!tool.enabled" :busy="toolStore.running" @click="toolStore.runDryRun(tool.tool_name)">
              Dry-run
            </SakuraButton>
          </article>
          <p v-if="!toolStore.filteredItems.length" class="tools-page__empty">无匹配工具。</p>
        </div>

        <div class="tools-page__subgrid">
          <section aria-label="工具审计">
            <h3>审计</h3>
            <ol>
              <li v-for="entry in toolStore.auditItems.slice(0, 4)" :key="entry.audit_entry_id">
                {{ entry.action }} · {{ entry.tool_name || entry.actor }}
              </li>
            </ol>
          </section>
          <section aria-label="安全授权">
            <h3>授权</h3>
            <ol>
              <li v-for="grant in toolStore.grants" :key="grant.grant_id">
                {{ grant.capability }} · {{ grant.scope_hash }}
              </li>
            </ol>
          </section>
        </div>
      </SakuraSettingsSection>

      <SakuraSettingsSection title="插件">
        <div class="tools-page__toolbar">
          <SakuraSegmentedControl v-model="pluginStore.filter" label="插件筛选" :options="pluginFilterOptions" />
          <SakuraButton :busy="pluginStore.scanning" @click="pluginStore.refresh()">扫描</SakuraButton>
        </div>

        <p class="tools-page__status" role="status" aria-live="polite">
          {{ pluginStore.lastSummary || `状态：${pluginStore.status}` }}<span v-if="pluginStore.importing"> · {{ pluginStore.importProgress }}%</span>
        </p>
        <p v-if="pluginStore.error" class="tools-page__error">{{ pluginStore.error.user_message }}</p>

        <div class="tools-page__rows" role="list" aria-label="插件列表">
          <article
            v-for="plugin in pluginStore.filteredItems"
            :key="plugin.plugin_id"
            class="tools-page__row"
            role="listitem"
          >
            <div class="tools-page__row-main">
              <strong>{{ plugin.plugin_id }}</strong>
              <span>{{ plugin.worker_state }}</span>
            </div>
            <div class="tools-page__badges">
              <span :class="{ muted: !plugin.enabled }">{{ plugin.enabled ? "启用" : "禁用" }}</span>
              <span>{{ plugin.loaded ? "已加载" : "未加载" }}</span>
            </div>
            <SakuraButton v-if="plugin.enabled" @click="pluginStore.disable(plugin.plugin_id)">停用</SakuraButton>
            <div v-else class="tools-page__inline-confirm">
              <SakuraInput
                :id="`plugin-confirm-${plugin.plugin_id}`"
                label="确认令牌"
                :model-value="pluginStore.confirmTokens[plugin.plugin_id] ?? ''"
                @update:model-value="pluginStore.setEnableConfirmToken(plugin.plugin_id, $event)"
              />
              <SakuraButton
                :disabled="!pluginStore.confirmTokens[plugin.plugin_id]?.trim()"
                @click="pluginStore.enable(plugin.plugin_id)"
              >
                启用
              </SakuraButton>
            </div>
          </article>
          <p v-if="!pluginStore.filteredItems.length" class="tools-page__empty">无匹配插件。</p>
        </div>
      </SakuraSettingsSection>

      <SakuraSettingsSection title="MCP">
        <div class="tools-page__toolbar">
          <SakuraSegmentedControl v-model="mcpStore.filter" label="MCP 筛选" :options="mcpFilterOptions" />
          <SakuraButton :busy="mcpStore.refreshing" @click="mcpStore.refresh()">刷新</SakuraButton>
        </div>

        <p class="tools-page__status" role="status" aria-live="polite">
          {{ mcpStore.lastToolResult || `状态：${mcpStore.status}` }}
        </p>
        <p v-if="mcpStore.error" class="tools-page__error">{{ mcpStore.error.user_message }}</p>

        <div class="tools-page__rows" role="list" aria-label="MCP 服务器列表">
          <article
            v-for="server in mcpStore.filteredServers"
            :key="server.server_id"
            class="tools-page__row"
            role="listitem"
          >
            <div class="tools-page__row-main">
              <strong>{{ server.server_id }}</strong>
              <span>{{ server.state }} · {{ server.tool_count }} tools</span>
            </div>
            <div class="tools-page__badges">
              <span :class="{ muted: !server.enabled }">{{ server.enabled ? "启用" : "禁用" }}</span>
            </div>
            <SakuraButton :disabled="!server.enabled" :busy="mcpStore.busy" @click="mcpStore.callEcho(server.server_id)">
              Echo
            </SakuraButton>
          </article>
          <p v-if="!mcpStore.filteredServers.length" class="tools-page__empty">无匹配服务器。</p>
        </div>
      </SakuraSettingsSection>
    </div>
  </section>
</template>

<style scoped>
.tools-page {
  display: grid;
  gap: var(--sakura-space-5);
  min-height: 100%;
}

.tools-page__header {
  display: flex;
  justify-content: space-between;
  gap: var(--sakura-space-5);
  align-items: end;
}

h1,
h3,
p,
dl,
dd {
  margin: 0;
}

.tools-page__header p,
.tools-page__status,
.tools-page__empty {
  color: var(--sakura-text-muted);
}

.tools-page__summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(68px, 1fr));
  gap: var(--sakura-space-2);
  min-width: min(420px, 100%);
}

.tools-page__summary div {
  min-height: 64px;
  display: grid;
  align-content: center;
  gap: var(--sakura-space-1);
  padding: var(--sakura-space-2);
  border: 1px solid rgba(212, 86, 122, 0.28);
  border-radius: var(--sakura-radius-md);
  background: rgba(255, 255, 255, 0.48);
}

.tools-page__summary dt {
  color: var(--sakura-text-muted);
  font-size: 0.84rem;
}

.tools-page__summary dd {
  font-size: 1.35rem;
  font-weight: 700;
}

.tools-page__grid {
  display: grid;
  gap: var(--sakura-space-5);
}

.tools-page__toolbar {
  display: flex;
  gap: var(--sakura-space-3);
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
}

.tools-page__rows {
  display: grid;
  gap: var(--sakura-space-2);
}

.tools-page__row {
  min-height: 66px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: var(--sakura-space-3);
  align-items: center;
  padding: var(--sakura-space-3) 0;
  border-top: 1px solid rgba(212, 86, 122, 0.18);
}

.tools-page__row-main {
  min-width: 0;
  display: grid;
  gap: var(--sakura-space-1);
}

.tools-page__row-main strong,
.tools-page__row-main span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tools-page__row-main span {
  color: var(--sakura-text-muted);
}

.tools-page__badges {
  display: flex;
  gap: var(--sakura-space-2);
  flex-wrap: wrap;
  justify-content: end;
}

.tools-page__badges span {
  min-height: 26px;
  display: inline-flex;
  align-items: center;
  padding: 0 var(--sakura-space-2);
  border: 1px solid rgba(212, 86, 122, 0.34);
  border-radius: var(--sakura-radius-sm);
  background: rgba(255, 255, 255, 0.5);
  white-space: nowrap;
}

.tools-page__badges .muted {
  color: var(--sakura-text-muted);
}

.tools-page__inline-confirm {
  min-width: min(260px, 100%);
  display: grid;
  grid-template-columns: minmax(120px, 1fr) auto;
  gap: var(--sakura-space-2);
  align-items: end;
}

.tools-page__subgrid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--sakura-space-4);
}

h3 {
  font-size: 0.95rem;
}

ol {
  margin: var(--sakura-space-2) 0 0;
  padding-left: var(--sakura-space-5);
  color: var(--sakura-text-muted);
}

li {
  overflow-wrap: anywhere;
}

.tools-page__error {
  color: var(--sakura-danger);
}

@media (max-width: 900px) {
  .tools-page__header,
  .tools-page__row {
    grid-template-columns: 1fr;
  }

  .tools-page__header {
    align-items: start;
  }

  .tools-page__summary,
  .tools-page__subgrid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .tools-page__badges {
    justify-content: start;
  }
}

@media (max-width: 520px) {
  .tools-page__summary,
  .tools-page__subgrid {
    grid-template-columns: 1fr;
  }
}
</style>
