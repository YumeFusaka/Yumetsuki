from __future__ import annotations

import importlib.util
from io import BytesIO
import os
from pathlib import Path
import sys
import time


_CUDA_DLL_DIRECTORY_HANDLES = []
_CUDA_DLL_DIRECTORY_PATHS: set[str] = set()
_CUDA_DLL_PATH_ENV_UPDATED = False


def _add_windows_cuda_dll_directories() -> None:
    global _CUDA_DLL_PATH_ENV_UPDATED
    if sys.platform != "win32":
        return
    candidates: list[Path] = []
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        candidates.append(Path(conda_prefix) / "Library" / "bin")
    for package in ("nvidia.cublas", "nvidia.cuda_runtime", "nvidia.cudnn"):
        try:
            spec = importlib.util.find_spec(package)
        except ModuleNotFoundError:
            continue
        if spec is None:
            continue
        package_dirs: list[Path] = []
        if spec.submodule_search_locations:
            package_dirs.extend(Path(location).resolve() for location in spec.submodule_search_locations)
        elif spec.origin is not None:
            package_dirs.append(Path(spec.origin).resolve().parent)
        for package_dir in package_dirs:
            candidates.extend((package_dir / "bin", package_dir / "lib"))
    for path in candidates:
        if path.exists():
            path_text = str(path)
            if path_text in _CUDA_DLL_DIRECTORY_PATHS:
                continue
            handle = os.add_dll_directory(path_text)
            _CUDA_DLL_DIRECTORY_HANDLES.append(handle)
            _CUDA_DLL_DIRECTORY_PATHS.add(path_text)
    if _CUDA_DLL_DIRECTORY_PATHS and not _CUDA_DLL_PATH_ENV_UPDATED:
        current_paths = os.environ.get("PATH", "").split(os.pathsep)
        normalized_current = {os.path.normcase(os.path.normpath(path)) for path in current_paths if path}
        prepend_paths = [
            path for path in sorted(_CUDA_DLL_DIRECTORY_PATHS)
            if os.path.normcase(os.path.normpath(path)) not in normalized_current
        ]
        if prepend_paths:
            os.environ["PATH"] = os.pathsep.join([*prepend_paths, os.environ.get("PATH", "")])
        _CUDA_DLL_PATH_ENV_UPDATED = True


_add_windows_cuda_dll_directories()


try:
    from faster_whisper import WhisperModel
except Exception:  # pragma: no cover - exercised when dependency is absent in user env
    WhisperModel = None

from config.schema import ASRConfig
from core.log_types import LogChannel, LogLevel, build_log_event
from core.model_catalog import STT_MODELS_DIR, resolve_model_path
from stt.adapter import STTAdapter
from stt.types import STTResult


class FasterWhisperAdapter(STTAdapter):
    def __init__(self, config: ASRConfig, log_service=None, session_id: str = ""):
        self._model_path = (config.model_path or "data/models/stt/faster-whisper-large-v3-turbo").strip()
        self._device = (config.device or "cpu").strip()
        self._effective_device = "cpu" if self._device.lower() == "auto" else self._device
        self._compute_type = (config.compute_type or "int8").strip()
        self._language = (config.language or "zh").strip()
        self._log_service = log_service
        self._session_id = session_id or "default-session"
        self._model = None

    def transcribe_wav(self, audio: bytes) -> STTResult:
        if not audio:
            return STTResult(text="", language=self._language, error="录音内容为空")

        started_at = time.monotonic()
        self._record_log_event(
            level=LogLevel.INFO,
            event_type="stt.transcribe_started",
            summary="STT transcription started",
            details={
                "audio_bytes": len(audio),
                "language": self._language,
                "model_path": self._model_path,
                "device": self._device,
                "effective_device": self._effective_device,
                "compute_type": self._compute_type,
            },
        )
        try:
            model = self._load_model()
            wav_file = BytesIO(audio)
            wav_file.name = "speech.wav"
            segments, info = model.transcribe(
                wav_file,
                language=self._transcribe_language(),
                vad_filter=True,
                beam_size=1,
                best_of=1,
                condition_on_previous_text=False,
            )
            text = "".join(segment.text for segment in segments).strip()
        except Exception as exc:
            error_message = self._format_error(exc)
            self._record_log_event(
                level=LogLevel.ERROR,
                event_type="stt.transcribe_failed",
                summary="STT transcription failed",
                details={"error": error_message, "elapsed_ms": int((time.monotonic() - started_at) * 1000)},
            )
            return STTResult(text="", language=self._language, error=error_message)

        if not text:
            self._record_log_event(
                level=LogLevel.WARN,
                event_type="stt.transcribe_empty",
                summary="STT transcription returned empty text",
                details={"elapsed_ms": int((time.monotonic() - started_at) * 1000)},
            )
            return STTResult(text="", language=self._language, error="未识别到语音")
        language = getattr(info, "language", "") or self._language
        self._record_log_event(
            level=LogLevel.INFO,
            event_type="stt.transcribe_completed",
            summary="STT transcription completed",
            details={
                "language": language,
                "text_length": len(text),
                "elapsed_ms": int((time.monotonic() - started_at) * 1000),
            },
        )
        return STTResult(text=text, language=language)

    def _load_model(self):
        if self._model is not None:
            return self._model
        _add_windows_cuda_dll_directories()
        if WhisperModel is None:
            raise RuntimeError("缺少 faster-whisper 依赖，请先安装 faster-whisper")
        model_path = resolve_model_path(self._model_path, STT_MODELS_DIR)
        if not model_path.exists():
            raise FileNotFoundError(f"STT 模型目录不存在：{self._model_path}")
        started_at = time.monotonic()
        self._record_log_event(
            level=LogLevel.INFO,
            event_type="stt.model_load_started",
            summary="STT model load started",
            details={
                "model_path": self._model_path,
                "resolved_model_path": str(model_path),
                "device": self._device,
                "effective_device": self._effective_device,
                "compute_type": self._compute_type,
            },
        )
        self._model = WhisperModel(
            str(model_path),
            device=self._effective_device,
            compute_type=self._compute_type,
            local_files_only=True,
        )
        self._record_log_event(
            level=LogLevel.INFO,
            event_type="stt.model_load_completed",
            summary="STT model load completed",
            details={"elapsed_ms": int((time.monotonic() - started_at) * 1000)},
        )
        return self._model

    def _transcribe_language(self) -> str | None:
        language = self._language.strip().lower()
        if not language or language == "auto":
            return None
        return self._language

    def _format_error(self, exc: Exception) -> str:
        message = str(exc)
        lowered = message.lower()
        if (
            ("cublas64_12.dll" in lowered or "cudart64_12.dll" in lowered or "cudnn" in lowered)
            and ("not found" in lowered or "cannot be loaded" in lowered or "找不到" in lowered)
        ):
            return (
                "CUDA 运行库缺失，无法使用 GPU 识别。"
                "请在 ASR 设置中把设备改为 cpu，或安装匹配 CUDA 12 的 NVIDIA 运行库。"
                f"原始错误：{message}"
            )
        return message

    def _record_log_event(self, level: LogLevel, event_type: str, summary: str, details: dict) -> None:
        if self._log_service is None:
            return
        self._log_service.record(
            build_log_event(
                channel=LogChannel.SYSTEM,
                level=level,
                source="stt.faster_whisper",
                event_type=event_type,
                session_id=self._session_id,
                summary=summary,
                details=details,
            )
        )
