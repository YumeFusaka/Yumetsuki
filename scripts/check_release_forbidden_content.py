from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


TEXT_EXTENSIONS = {
    ".cfg",
    ".conf",
    ".css",
    ".csv",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsonl",
    ".lock",
    ".md",
    ".py",
    ".rs",
    ".toml",
    ".txt",
    ".ts",
    ".tsx",
    ".vue",
    ".yaml",
    ".yml",
}
MAX_TEXT_BYTES = 1024 * 1024


@dataclass(frozen=True)
class Finding:
    path: Path
    rule_id: str
    snippet: str = ""


SECRET_PATTERNS = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE)),
    ("authorization_secret", re.compile(r"authorization\s*[:=]\s*(bearer\s+)?[A-Za-z0-9._\-]{16,}", re.IGNORECASE)),
    ("cookie_secret", re.compile(r"cookie\s*[:=]\s*[^;\r\n]{12,}", re.IGNORECASE)),
    ("bearer_token", re.compile(r"bearer\s+[A-Za-z0-9._\-]{24,}", re.IGNORECASE)),
    ("openai_token", re.compile(r"sk-[A-Za-z0-9_\-]{16,}", re.IGNORECASE)),
    ("generic_token", re.compile(r"\b(token|api[_-]?key|secret)\s*[:=]\s*[A-Za-z0-9._\-]{16,}", re.IGNORECASE)),
    ("localhost_url", re.compile(r"https?://(localhost|127\.0\.0\.1)(:\d+)?/[^\s'\"]+", re.IGNORECASE)),
    ("windows_user_path", re.compile(r"[A-Za-z]:\\Users\\[^\\\r\n]+\\[^\r\n]+")),
]


def _relative_parts(path: Path, root: Path) -> tuple[str, ...]:
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path
    return tuple(part.lower() for part in relative.parts)


def _path_rule(path: Path, root: Path) -> str | None:
    parts = _relative_parts(path, root)
    name = path.name.lower()
    suffix = path.suffix.lower()
    joined = "/".join(parts)

    if name == ".env" or name.startswith(".env."):
        return "env_file"
    if "pyside6" in parts or "pyside6" in name:
        return "pyside6"
    if name.startswith("qt") and suffix in {".dll", ".pyd", ".so", ".dylib"}:
        return "qt_runtime"
    if "qtwebengine" in joined:
        return "qtwebengine"
    if parts[:1] == ("ui",) or "/ui/" in f"/{joined}/":
        return "legacy_ui"
    if parts[:3] == ("data", "config", "api.yaml") or parts[:3] == ("data", "config", "memory.yaml"):
        return "runtime_config"
    if len(parts) >= 2 and parts[:2] == ("data", "logs"):
        return "runtime_log"
    if len(parts) >= 2 and parts[:2] == ("data", "memory"):
        return "runtime_memory"
    if len(parts) >= 2 and parts[:2] == ("data", "browser_sessions"):
        return "browser_profile"
    if len(parts) >= 2 and parts[:2] == ("data", "models"):
        return "model_cache"
    if suffix in {".png", ".jpg", ".jpeg", ".webp"} and ("vision" in parts or name.startswith("screen_")):
        return "screenshot"
    if suffix in {".wav", ".mp3", ".flac", ".ogg"}:
        return "audio_artifact"
    return None


def _is_text_candidate(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    return path.name.lower() in {"cargo.lock", "package-lock.json", "requirements-sidecar.txt"}


def _redact(snippet: str) -> str:
    snippet = snippet.replace("\r", " ").replace("\n", " ")
    for _, pattern in SECRET_PATTERNS:
        snippet = pattern.sub("<redacted>", snippet)
    if len(snippet) > 120:
        snippet = snippet[:117] + "..."
    return snippet


def _scan_text(path: Path) -> list[Finding]:
    if not _is_text_candidate(path):
        return []
    try:
        if path.stat().st_size > MAX_TEXT_BYTES:
            return []
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    findings: list[Finding] = []
    for rule_id, pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            findings.append(Finding(path, rule_id, _redact(match.group(0))))
    return findings


def scan_bundle(bundle: Path) -> list[Finding]:
    root = bundle.resolve()
    findings: list[Finding] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        path_rule = _path_rule(path, root)
        if path_rule:
            findings.append(Finding(path, path_rule))
        findings.extend(_scan_text(path))
    return findings


def _format_finding(finding: Finding, root: Path) -> str:
    try:
        rel = finding.path.relative_to(root)
    except ValueError:
        rel = finding.path
    snippet = f" snippet={finding.snippet}" if finding.snippet else ""
    return f"{rel}: {finding.rule_id}{snippet}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="扫描发布包中的禁止内容")
    parser.add_argument("--bundle", type=Path, default=Path("apps/desktop/src-tauri/target/release/bundle"))
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args(argv)

    bundle = args.bundle
    if not bundle.exists():
        if args.allow_missing:
            print(f"bundle 不存在，按 --allow-missing 跳过: {bundle}")
            return 0
        print(f"bundle 不存在: {bundle}", file=sys.stderr)
        return 1
    if not bundle.is_dir():
        print(f"bundle 不是目录: {bundle}", file=sys.stderr)
        return 1

    findings = scan_bundle(bundle)
    if findings:
        root = bundle.resolve()
        for finding in findings:
            print(_format_finding(finding, root), file=sys.stderr)
        return 1

    print("未发现禁止内容")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
