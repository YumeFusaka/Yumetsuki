param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$TempRoot = [System.IO.Path]::GetTempPath()
$Venv = Join-Path $TempRoot ("yumetsuki-sidecar-smoke-" + [System.Guid]::NewGuid().ToString("N"))

function Invoke-Checked {
    param([string[]]$CommandArgs)
    & $CommandArgs[0] @($CommandArgs[1..($CommandArgs.Length - 1)])
    if ($LASTEXITCODE -ne 0) {
        throw "命令失败：$($CommandArgs -join ' ')"
    }
}

try {
    Invoke-Checked @($Python, "-m", "venv", $Venv)
    $VenvPython = Join-Path $Venv "Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        $VenvPython = Join-Path $Venv "bin/python"
    }

    Invoke-Checked @(
        $VenvPython,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "-r",
        (Join-Path $Root "requirements-sidecar.txt")
    )

    Invoke-Checked @(
        $VenvPython,
        "-c",
        "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('PySide6') is None else 1)"
    )

    $env:YUMETSUKI_ROOT = $Root
    $Smoke = @"
import json
import os
import subprocess
import sys

root = os.environ["YUMETSUKI_ROOT"]
request = {
    "kind": "request",
    "request_id": "req_no_pyside6_smoke",
    "method": "sidecar.hello",
    "params": {"supported_protocol_versions": [1]},
    "protocol_version": 1,
    "trace_id": "trace_no_pyside6_smoke",
    "parent_trace_id": None,
    "session_id": "sess_no_pyside6_smoke",
    "deadline_ms": 30000,
}
payload = json.dumps(request, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n"
completed = subprocess.run(
    [sys.executable, "-m", "python_core.sidecar_main", "--stdio"],
    cwd=root,
    input=payload,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    check=False,
)
if completed.returncode != 0:
    sys.stderr.write(completed.stderr.decode("utf-8", errors="replace"))
    raise SystemExit(completed.returncode)
lines = [line for line in completed.stdout.splitlines() if line.strip()]
if not lines:
    sys.stderr.write("sidecar stdout 没有协议帧\n")
    raise SystemExit(1)
frames = []
for line in lines:
    try:
        frame = json.loads(line.decode("utf-8"))
    except Exception as exc:
        sys.stderr.write(f"sidecar stdout 非协议帧: {line!r}; {exc}\n")
        raise SystemExit(1)
    if frame.get("kind") not in {"response", "event"}:
        sys.stderr.write(f"sidecar stdout 帧类型异常: {frame!r}\n")
        raise SystemExit(1)
    frames.append(frame)
response = next((frame for frame in frames if frame.get("kind") == "response"), None)
if response is None or not response.get("ok"):
    sys.stderr.write(f"sidecar hello 失败: {response!r}\n")
    raise SystemExit(1)
if response["result"].get("selected_protocol_version") != 1:
    sys.stderr.write(f"sidecar 协议版本异常: {response!r}\n")
    raise SystemExit(1)
if b"PySide6" in completed.stderr or b"QApplication" in completed.stderr:
    sys.stderr.write("sidecar stderr 命中 PySide6/QApplication\n")
    raise SystemExit(1)
print("no-PySide6 sidecar smoke 通过")
"@

    $SmokePath = Join-Path $Venv "no_pyside6_sidecar_smoke.py"
    Set-Content -LiteralPath $SmokePath -Value $Smoke -Encoding UTF8
    Invoke-Checked @($VenvPython, $SmokePath)
}
finally {
    if ($Venv -and (Test-Path -LiteralPath $Venv) -and $Venv.StartsWith($TempRoot)) {
        Remove-Item -LiteralPath $Venv -Recurse -Force
    }
}
