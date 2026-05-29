import { describe, expect, it } from "vitest";
import {
  assertPersistableField,
  GLOBAL_FORBIDDEN_PERSISTENCE_FIELDS,
  PERSISTENCE_ALLOWLIST
} from "./allowlist";

describe("persistence allowlist", () => {
  it("覆盖当前桌面壳要求的 store", () => {
    expect(Object.keys(PERSISTENCE_ALLOWLIST).sort()).toEqual([
      "characterStore",
      "diagnosticStore",
      "logStore",
      "mcpStore",
      "pluginStore",
      "themeStore",
      "toolStore",
      "windowStore"
    ]);
  });

  it("允许字段和禁止字段互斥", () => {
    for (const rule of Object.values(PERSISTENCE_ALLOWLIST)) {
      for (const forbidden of rule.forbiddenFields) {
        expect(rule.allowedFields).not.toContain(forbidden);
      }
    }
  });

  it("诊断报告路径、运行中 request 和 token 不可持久化", () => {
    expect(assertPersistableField("diagnosticStore", "reportPath")).toBe(false);
    expect(assertPersistableField("windowStore", "request")).toBe(false);
    expect(assertPersistableField("toolStore", "confirmToken")).toBe(false);
    expect(assertPersistableField("pluginStore", "confirmTokens")).toBe(false);
    expect(GLOBAL_FORBIDDEN_PERSISTENCE_FIELDS).toContain("api_key");
    expect(GLOBAL_FORBIDDEN_PERSISTENCE_FIELDS).toContain("diagnostic_report_path");
  });
});
