export type AppRouteName = "chat" | "settings" | "logs" | "tools" | "diagnostics";

export interface AppRoute {
  name: AppRouteName;
  path: string;
  label: string;
  disabled?: boolean;
}

export const APP_ROUTES: AppRoute[] = [
  { name: "chat", path: "/chat", label: "聊天" },
  { name: "settings", path: "/settings", label: "设置" },
  { name: "logs", path: "/logs/system", label: "日志" },
  { name: "tools", path: "/tools/plugins", label: "工具" },
  { name: "diagnostics", path: "/diagnostics", label: "诊断" }
];

export function resolveRoute(pathname = window.location.pathname): AppRouteName {
  if (pathname.startsWith("/settings")) {
    return "settings";
  }
  if (pathname.startsWith("/logs")) {
    return "logs";
  }
  if (pathname.startsWith("/tools")) {
    return "tools";
  }
  if (pathname.startsWith("/diagnostics")) {
    return "diagnostics";
  }
  return "chat";
}

export function navigateTo(path: string): void {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}
