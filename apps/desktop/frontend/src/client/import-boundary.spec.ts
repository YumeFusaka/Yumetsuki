import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}

describe("frontend import boundary", () => {
  it("只有 typed client 层可 import Tauri API，且业务代码不使用 axios/fetch", () => {
    const srcRoot = join(process.cwd(), "src");
    const failures: string[] = [];

    for (const file of walk(srcRoot)) {
      if (!/\.(ts|vue)$/.test(file)) {
        continue;
      }
      const rel = relative(process.cwd(), file).replaceAll("\\", "/");
      const text = readFileSync(file, "utf8");
      if (!rel.startsWith("src/client/") && text.includes("@tauri-apps/api")) {
        failures.push(`${rel} 越界 import @tauri-apps/api`);
      }
      if (!rel.endsWith("import-boundary.spec.ts") && text.includes("axios")) {
        failures.push(`${rel} 使用 axios`);
      }
      if (!rel.includes(".spec.") && !rel.startsWith("src/client/") && /\bfetch\s*\(/.test(text)) {
        failures.push(`${rel} 直接 fetch`);
      }
    }

    expect(failures).toEqual([]);
  });
});
