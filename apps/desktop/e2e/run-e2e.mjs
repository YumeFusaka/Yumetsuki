import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";

const suites = new Map([
  ["a11y", "a11y.spec.ts"],
  ["startup", "startup.spec.ts"],
  ["smoke", "smoke.spec.ts"],
  ["settings", "settings.spec.ts"],
  ["chat", "chat.spec.ts"],
  ["logs-tools", "logs-tools.spec.ts"],
  ["stress", "stress.spec.ts"],
  ["responsive", "responsive.spec.ts"]
]);

const suite = process.argv[2];
const spec = suites.get(suite);

if (!spec) {
  console.error(`未知 E2E 套件: ${suite ?? "<empty>"}`);
  process.exit(1);
}

const cliCandidates = [
  resolve("node_modules/@playwright/test/cli.js"),
  resolve("frontend/node_modules/@playwright/test/cli.js")
];
const cli = cliCandidates.find((candidate) => existsSync(candidate));

if (!cli) {
  console.error(`E2E_BLOCKED ${suite}: 未安装 @playwright/test；请在用户确认安装依赖后运行真实 E2E。`);
  process.exit(2);
}

const result = spawnSync(process.execPath, [cli, "test", `e2e/${spec}`], {
  stdio: "inherit",
  shell: false
});

process.exit(result.status ?? 1);
