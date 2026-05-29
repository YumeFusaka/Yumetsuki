export interface PersistenceRule {
  store: string;
  storageKey: string;
  version: 1;
  allowedFields: string[];
  forbiddenFields: string[];
}

export const GLOBAL_FORBIDDEN_PERSISTENCE_FIELDS = [
  "api_key",
  "authorization",
  "cookie",
  "model_path",
  "screenshot_path",
  "ocr_text",
  "tool_command",
  "request_id",
  "confirm_token",
  "audio_state",
  "stt_temp",
  "browser_profile_path",
  "diagnostic_report_path"
] as const;

export const PERSISTENCE_ALLOWLIST: Record<string, PersistenceRule> = {
  windowStore: {
    store: "windowStore",
    storageKey: "yumetsuki.window.v1",
    version: 1,
    allowedFields: ["position", "size", "scale", "alwaysOnTop", "transparent"],
    forbiddenFields: ["request", "handle", "screenshotPath"]
  },
  themeStore: {
    store: "themeStore",
    storageKey: "yumetsuki.theme.v1",
    version: 1,
    allowedFields: ["themeName", "fontFamily", "fontScale", "bubbleScale"],
    forbiddenFields: ["tokenOverride", "runtimeError"]
  },
  logStore: {
    store: "logStore",
    storageKey: "yumetsuki.logs.v1",
    version: 1,
    allowedFields: ["channel", "source", "level", "followBottom", "columnWidths"],
    forbiddenFields: ["entries", "selectedDetail", "trace"]
  },
  toolStore: {
    store: "toolStore",
    storageKey: "yumetsuki.tools.v1",
    version: 1,
    allowedFields: ["grantSummaries", "filter", "expandedIds"],
    forbiddenFields: ["commandText", "env", "cwd", "confirmToken"]
  },
  pluginStore: {
    store: "pluginStore",
    storageKey: "yumetsuki.plugins.v1",
    version: 1,
    allowedFields: ["filter", "expandedIds", "enabledPluginIds"],
    forbiddenFields: ["stdout", "stderr", "manifestPath", "confirmToken", "confirmTokens"]
  },
  mcpStore: {
    store: "mcpStore",
    storageKey: "yumetsuki.mcp.v1",
    version: 1,
    allowedFields: ["serverSummaries", "filter", "expandedIds"],
    forbiddenFields: ["argv", "cwd", "env", "stdioOutput", "confirmToken"]
  },
  diagnosticStore: {
    store: "diagnosticStore",
    storageKey: "yumetsuki.diagnostics.v1",
    version: 1,
    allowedFields: ["recentChecks", "exportFormat"],
    forbiddenFields: ["reportPath", "logText", "redactionHitContent"]
  },
  characterStore: {
    store: "characterStore",
    storageKey: "yumetsuki.character.v1",
    version: 1,
    allowedFields: ["recentCharacterId", "displayPreferences"],
    forbiddenFields: ["characterFileText", "fullLocalPath"]
  }
};

export function assertPersistableField(store: string, field: string): boolean {
  const rule = PERSISTENCE_ALLOWLIST[store];
  if (!rule) {
    return false;
  }
  return rule.allowedFields.includes(field) && !rule.forbiddenFields.includes(field);
}
