import { createRouter, createWebHistory } from 'vue-router'

const ChatView = { template: '<main data-testid="chat-route"><slot /></main>' }
const SettingsView = { template: '<main data-testid="settings-route"><slot /></main>' }
const LogsView = { template: '<main data-testid="logs-route"><slot /></main>' }
const ToolsView = { template: '<main data-testid="tools-route"><slot /></main>' }
const DiagnosticsView = { template: '<main data-testid="diagnostics-route"><slot /></main>' }

export const routeMatrix = [
  { name: 'settings', path: '/settings/:section?', ownerStores: ['configStore', 'characterStore'] },
  { name: 'chat', path: '/chat', ownerStores: ['chatStore', 'audioStore', 'sttStore', 'windowStore'] },
  { name: 'logs-conversation', path: '/logs/conversation', ownerStores: ['logStore'] },
  { name: 'logs-system', path: '/logs/system', ownerStores: ['logStore'] },
  { name: 'tools-plugins', path: '/tools/plugins', ownerStores: ['pluginStore'] },
  { name: 'tools-mcp', path: '/tools/mcp', ownerStores: ['mcpStore'] },
  { name: 'diagnostics', path: '/diagnostics', ownerStores: ['diagnosticStore'] },
] as const

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/chat' },
    { path: '/chat', name: 'chat', component: ChatView },
    { path: '/settings/:section?', name: 'settings', component: SettingsView },
    { path: '/logs/conversation', name: 'logs-conversation', component: LogsView },
    { path: '/logs/system', name: 'logs-system', component: LogsView },
    { path: '/tools/plugins', name: 'tools-plugins', component: ToolsView },
    { path: '/tools/mcp', name: 'tools-mcp', component: ToolsView },
    { path: '/diagnostics', name: 'diagnostics', component: DiagnosticsView },
  ],
})
