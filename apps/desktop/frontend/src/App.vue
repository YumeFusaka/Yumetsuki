<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import ChatPanel from "./components/ChatPanel.vue";
import DiagnosticsPage from "./pages/DiagnosticsPage.vue";
import LogsPage from "./pages/LogsPage.vue";
import SettingsPage from "./pages/SettingsPage.vue";
import ToolsPage from "./pages/ToolsPage.vue";
import { APP_ROUTES, navigateTo, resolveRoute, type AppRouteName } from "./router";
import { useAppStore } from "./stores/appStore";
import { useThemeStore } from "./stores/themeStore";

const appStore = useAppStore();
const themeStore = useThemeStore();
const currentRoute = ref<AppRouteName>(resolveRoute());

const currentComponent = computed(() => {
  if (currentRoute.value === "settings") {
    return SettingsPage;
  }
  if (currentRoute.value === "logs") {
    return LogsPage;
  }
  if (currentRoute.value === "tools") {
    return ToolsPage;
  }
  if (currentRoute.value === "diagnostics") {
    return DiagnosticsPage;
  }
  return ChatPanel;
});

function onPopState() {
  currentRoute.value = resolveRoute();
}

function go(path: string, disabled?: boolean) {
  if (disabled) {
    return;
  }
  navigateTo(path);
}

onMounted(() => {
  themeStore.init();
  void appStore.init();
  window.addEventListener("popstate", onPopState);
});

onBeforeUnmount(() => {
  window.removeEventListener("popstate", onPopState);
  appStore.dispose();
  themeStore.dispose();
});
</script>

<template>
  <div class="app-shell" role="application" aria-label="Yumetsuki 桌面壳">
    <aside class="app-shell__rail">
      <div class="app-shell__brand" aria-label="Yumetsuki">
        <span aria-hidden="true">夢</span>
        <strong>Yumetsuki</strong>
      </div>

      <nav class="app-shell__nav" aria-label="主导航">
        <a
          v-for="route in APP_ROUTES"
          :key="route.name"
          :href="route.path"
          :aria-current="currentRoute === route.name ? 'page' : undefined"
          :aria-disabled="route.disabled ? 'true' : undefined"
          @click.prevent="go(route.path, route.disabled)"
        >
          {{ route.label }}
        </a>
      </nav>

      <section class="app-shell__startup" aria-label="启动状态">
        <span data-testid="startup-status">{{ appStore.statusText }}</span>
        <small>schema: {{ appStore.schemaHash || "pending" }}</small>
      </section>
    </aside>

    <main class="app-shell__main">
      <component :is="currentComponent" />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  color: var(--sakura-text);
}

.app-shell__rail {
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: var(--sakura-space-5);
  min-height: 100vh;
  padding: var(--sakura-space-5);
  border-right: 1px solid rgba(212, 86, 122, 0.28);
  background: rgba(255, 255, 255, 0.34);
  backdrop-filter: blur(16px);
}

.app-shell__brand {
  display: flex;
  align-items: center;
  gap: var(--sakura-space-2);
}

.app-shell__brand span {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border: 2px solid var(--sakura-border-strong);
  border-radius: 50%;
  color: var(--sakura-accent-strong);
  background: rgba(255, 255, 255, 0.72);
}

.app-shell__nav {
  display: grid;
  align-content: start;
  gap: var(--sakura-space-2);
}

.app-shell__nav a {
  min-height: 40px;
  display: flex;
  align-items: center;
  padding: 0 var(--sakura-space-3);
  border: 2px solid transparent;
  border-radius: var(--sakura-radius-md);
  text-decoration: none;
  overflow-wrap: anywhere;
}

.app-shell__nav a[aria-current="page"] {
  border-color: var(--sakura-border-strong);
  background: rgba(255, 255, 255, 0.66);
}

.app-shell__nav a[aria-disabled="true"] {
  opacity: 0.48;
  cursor: not-allowed;
}

.app-shell__startup {
  display: grid;
  gap: var(--sakura-space-1);
  padding: var(--sakura-space-3);
  border: 2px solid var(--sakura-border);
  border-radius: var(--sakura-radius-md);
  background: rgba(255, 255, 255, 0.54);
}

.app-shell__startup small {
  color: var(--sakura-text-muted);
  overflow-wrap: anywhere;
}

.app-shell__main {
  min-width: 0;
  min-height: 100vh;
  padding: var(--sakura-space-6);
}

@media (max-width: 820px) {
  .app-shell {
    grid-template-columns: 1fr;
  }

  .app-shell__rail {
    min-height: auto;
    grid-template-rows: auto auto auto;
    border-right: 0;
    border-bottom: 1px solid rgba(212, 86, 122, 0.28);
  }

  .app-shell__nav {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .app-shell__main {
    min-height: auto;
    padding: var(--sakura-space-4);
  }
}
</style>
