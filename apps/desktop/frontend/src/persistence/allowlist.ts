export interface PersistenceRule {
  storageKey: string
  version: number
  allow: string[]
}

export const persistenceAllowlist = {
  windowStore: {
    storageKey: 'yumetsuki.window.v1',
    version: 1,
    allow: ['position', 'size', 'scale', 'alwaysOnTop', 'transparentPreference'],
  },
  themeStore: {
    storageKey: 'yumetsuki.theme.v1',
    version: 1,
    allow: ['themeName', 'fontFamily', 'fontScale'],
  },
  logStore: {
    storageKey: 'yumetsuki.logs.v1',
    version: 1,
    allow: ['channel', 'source', 'level', 'followBottom', 'columnWidths'],
  },
  toolStore: {
    storageKey: 'yumetsuki.tools.v1',
    version: 1,
    allow: ['grantSummary', 'filter', 'expanded'],
  },
  pluginStore: {
    storageKey: 'yumetsuki.plugins.v1',
    version: 1,
    allow: ['filter', 'expanded', 'enabledPluginIdSummary'],
  },
  mcpStore: {
    storageKey: 'yumetsuki.mcp.v1',
    version: 1,
    allow: ['serverIdSummary', 'filter', 'expanded'],
  },
  diagnosticStore: {
    storageKey: 'yumetsuki.diagnostics.v1',
    version: 1,
    allow: ['recentCheckSelection', 'exportFormatPreference'],
  },
  characterStore: {
    storageKey: 'yumetsuki.character.v1',
    version: 1,
    allow: ['recentCharacterId', 'displayPreference'],
  },
  chatStore: {
    storageKey: 'yumetsuki.chat.v1',
    version: 1,
    allow: [],
  },
} satisfies Record<string, PersistenceRule>

export const persistenceDeniedKeys = {
  windowStore: ['request', 'handle', 'screenshotPath'],
  themeStore: ['temporaryTokenOverride', 'runtimeError'],
  logStore: ['body', 'detail', 'fullTrace'],
  toolStore: ['commandText', 'env', 'cwd', 'token'],
  pluginStore: ['stdout', 'stderr', 'manifestLocalPath', 'confirmToken'],
  mcpStore: ['argv', 'cwd', 'env', 'stdioOutput', 'confirmToken'],
  diagnosticStore: ['diagnosticPackagePath', 'logBody', 'sensitiveScanHit'],
  characterStore: ['characterFileBody', 'fullLocalPath'],
  chatStore: ['inputDraft', 'apiKey', 'authorization', 'cookie', 'runningRequest', 'confirmToken'],
} as const
