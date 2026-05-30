<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { SCHEMA_HASH } from './client/types/rpc'
import ChatPanel from './components/ChatPanel.vue'
import VirtualLogList from './components/VirtualLogList.vue'

const route = useRoute()
const routePath = computed(() => route.path)
</script>

<template>
  <div class="app-shell">
    <nav class="app-shell__nav" aria-label="主导航">
      <strong>Yumetsuki</strong>
      <RouterLink to="/chat">聊天</RouterLink>
      <RouterLink to="/settings/api">设置</RouterLink>
      <RouterLink to="/logs/conversation">对话日志</RouterLink>
      <RouterLink to="/logs/system">平台日志</RouterLink>
      <RouterLink to="/tools/plugins">插件</RouterLink>
      <RouterLink to="/tools/mcp">MCP</RouterLink>
      <RouterLink to="/diagnostics">诊断</RouterLink>
    </nav>

    <main class="app-shell__content" data-testid="first-screen">
      <section v-if="routePath.startsWith('/settings')" class="route-panel" data-testid="settings-page">
        <h1>设置中心</h1>
        <p>API、角色、记忆、Agent、插件、MCP、日志、诊断、系统入口已保留；Phase 2 起逐页迁移真实表单。</p>
        <button type="button" disabled>保存 API 配置</button>
        <button type="button" disabled>保存系统配置</button>
      </section>

      <section v-else-if="routePath.startsWith('/logs')" class="route-panel">
        <h1>{{ routePath.includes('system') ? '平台日志' : '对话日志' }}</h1>
        <VirtualLogList />
      </section>

      <section v-else-if="routePath.startsWith('/tools')" class="route-panel">
        <h1>{{ routePath.includes('mcp') ? 'MCP' : '插件' }}</h1>
        <p>未迁移入口保持禁用占位，Phase 4 接入权限确认与运行状态。</p>
        <button type="button" disabled>刷新</button>
      </section>

      <section v-else-if="routePath.startsWith('/diagnostics')" class="route-panel" data-testid="diagnostics-page">
        <h1>诊断</h1>
        <p>schema hash: <code data-testid="schema-hash">{{ SCHEMA_HASH }}</code></p>
        <p>sidecar hello: ok</p>
        <button type="button" disabled>运行诊断</button>
      </section>

      <section v-else class="route-panel" data-testid="chat-page">
        <h1>聊天</h1>
        <ChatPanel />
        <VirtualLogList />
      </section>
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(156px, 180px) minmax(0, 1fr);
  background: var(--sakura-color-bg);
  color: var(--sakura-color-text);
  font-family: var(--sakura-font-family);
}

.app-shell__nav {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px 12px;
  border-right: 1px solid var(--sakura-color-border);
  background: rgba(255, 255, 255, 0.62);
}

.app-shell__nav a {
  min-height: 34px;
  padding: 8px 10px;
  border-radius: var(--sakura-radius-md);
  color: var(--sakura-color-text);
  text-decoration: none;
}

.app-shell__nav a.router-link-active {
  background: #f9dce4;
  color: var(--sakura-color-primary-strong);
  font-weight: 700;
}

.app-shell__content {
  min-width: 0;
  padding: 18px;
}

.route-panel {
  display: grid;
  gap: 14px;
  max-width: 980px;
}

.route-panel h1 {
  margin: 0;
  font-size: 24px;
}

.route-panel p {
  overflow-wrap: anywhere;
}

button {
  width: fit-content;
  min-height: 34px;
  border: 1px solid var(--sakura-color-border);
  border-radius: var(--sakura-radius-md);
  padding: 0 12px;
}

@media (max-width: 620px) {
  .app-shell {
    grid-template-columns: 1fr;
  }

  .app-shell__nav {
    position: sticky;
    top: 0;
    z-index: 1;
    flex-direction: row;
    flex-wrap: wrap;
    border-right: 0;
    border-bottom: 1px solid var(--sakura-color-border);
  }
}
</style>
