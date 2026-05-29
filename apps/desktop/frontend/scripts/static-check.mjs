import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const srcRoot = join(root, "src");
const requiredFiles = [
  "package.json",
  "tsconfig.json",
  "vite.config.ts",
  "vitest.config.ts",
  "src/main.ts",
  "src/App.vue",
  "src/client/types/rpc.ts",
  "src/client/tauriClient.ts",
  "src/client/commands/config.ts",
  "src/client/commands/chat.ts",
  "src/client/commands/sidecar.ts",
  "src/client/events/index.ts",
  "src/stores/appStore.ts",
  "src/stores/chatStore.ts",
  "src/stores/configStore.ts",
  "src/stores/logStore.ts",
  "src/stores/themeStore.ts",
  "src/components/ChatPanel.vue",
  "src/components/VirtualLogList.vue",
  "src/persistence/allowlist.ts"
];

const failures = [];

for (const file of requiredFiles) {
  if (!existsSync(join(root, file))) {
    failures.push(`缺少文件: ${file}`);
  }
}

function walk(dir) {
  const entries = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) {
      entries.push(...walk(path));
    } else {
      entries.push(path);
    }
  }
  return entries;
}

for (const file of walk(srcRoot)) {
  if (!/\.(ts|vue)$/.test(file)) {
    continue;
  }
  const rel = relative(root, file).replaceAll("\\", "/");
  const text = readFileSync(file, "utf8");
  const mayUseTauri = rel.startsWith("src/client/");
  if (!mayUseTauri && text.includes("@tauri-apps/api")) {
    failures.push(`非 typed client 层 import @tauri-apps/api: ${rel}`);
  }
  if (!rel.endsWith("import-boundary.spec.ts") && text.includes("axios")) {
    failures.push(`禁止 axios: ${rel}`);
  }
  if (!rel.includes(".spec.") && !rel.startsWith("src/client/") && /\bfetch\s*\(/.test(text)) {
    failures.push(`业务代码禁止直接 fetch(): ${rel}`);
  }
}

const packageJson = JSON.parse(readFileSync(join(fileURLToPath(new URL("../..", import.meta.url)), "package.json"), "utf8"));
const expectedScripts = [
  "test",
  "test:a11y",
  "e2e:startup",
  "e2e:smoke",
  "e2e:settings",
  "e2e:chat",
  "e2e:logs-tools",
  "e2e:stress",
  "e2e:responsive"
];

for (const script of expectedScripts) {
  if (!packageJson.scripts?.[script]) {
    failures.push(`apps/desktop/package.json 缺少脚本: ${script}`);
  }
}

if (failures.length > 0) {
  console.error(failures.join("\n"));
  process.exit(1);
}

console.log("static-check passed");
