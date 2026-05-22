from __future__ import annotations

import subprocess

MAX_OUTPUT_LENGTH = 4096


def do_run_command(command: str, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout
        if result.stderr:
            output += "\n[stderr]\n" + result.stderr
        if len(output) > MAX_OUTPUT_LENGTH:
            output = output[:MAX_OUTPUT_LENGTH] + "\n...(输出已截断)"
        if not output.strip():
            return f"命令执行完成，退出码：{result.returncode}（无输出）"
        return output
    except subprocess.TimeoutExpired:
        return f"命令执行超时（{timeout}秒）：{command}"
    except OSError as e:
        return f"命令执行失败：{e}"
