from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TTSSegmentStatus(str, Enum):
    QUEUED = "queued"
    TRANSLATING = "translating"
    READY_FOR_TTS = "ready_for_tts"
    SYNTHESIZING = "synthesizing"
    STREAMING = "streaming"
    PLAYED = "played"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class TTSSegmentState:
    utterance_id: int
    segment_id: int
    text: str
    status: TTSSegmentStatus
    started_at: float | None = None


class TTSPipelineController:
    _TERMINAL_STATUSES = {
        TTSSegmentStatus.PLAYED,
        TTSSegmentStatus.FAILED,
        TTSSegmentStatus.TIMED_OUT,
        TTSSegmentStatus.SKIPPED,
        TTSSegmentStatus.CANCELLED,
    }

    def __init__(
        self,
        max_translation_workers: int,
        max_tts_workers: int,
        queue_limit: int,
        segment_total_timeout_seconds: int,
    ):
        self._max_translation_workers = max_translation_workers
        self._max_tts_workers = max_tts_workers
        self._queue_limit = max(1, queue_limit)
        self._segment_total_timeout_seconds = segment_total_timeout_seconds
        self._current_utterance_id = 0
        self.segments: dict[tuple[int, int], TTSSegmentState] = {}

    def begin_turn(self, utterance_id: int) -> None:
        self._current_utterance_id = utterance_id
        for segment in self.segments.values():
            if segment.utterance_id == utterance_id:
                continue
            if segment.status in self._TERMINAL_STATUSES:
                continue
            segment.status = TTSSegmentStatus.CANCELLED

    def enqueue_text_segment(
        self,
        utterance_id: int,
        segment_id: int,
        text: str,
        needs_translation: bool,
    ) -> TTSSegmentState:
        key = (utterance_id, segment_id)
        if self._count_live_segments(utterance_id) >= self._queue_limit:
            state = TTSSegmentState(
                utterance_id=utterance_id,
                segment_id=segment_id,
                text=text,
                status=TTSSegmentStatus.SKIPPED,
            )
            self.segments[key] = state
            return state

        state = TTSSegmentState(
            utterance_id=utterance_id,
            segment_id=segment_id,
            text=text,
            status=TTSSegmentStatus.TRANSLATING if needs_translation else TTSSegmentStatus.READY_FOR_TTS,
        )
        self.segments[key] = state
        return state

    def mark_ready_for_tts(self, key: tuple[int, int], text: str | None = None) -> None:
        state = self.segments.get(key)
        if state is None or state.status in self._TERMINAL_STATUSES:
            return
        if text is not None:
            state.text = text
        state.status = TTSSegmentStatus.READY_FOR_TTS

    def mark_synthesizing(self, key: tuple[int, int], started_at: float) -> None:
        state = self.segments.get(key)
        if state is None or state.status in self._TERMINAL_STATUSES:
            return
        state.status = TTSSegmentStatus.SYNTHESIZING
        state.started_at = started_at

    def mark_streaming(self, key: tuple[int, int]) -> None:
        state = self.segments.get(key)
        if state is None or state.status in self._TERMINAL_STATUSES:
            return
        state.status = TTSSegmentStatus.STREAMING

    def mark_played(self, key: tuple[int, int]) -> None:
        self._set_terminal_status(key, TTSSegmentStatus.PLAYED)

    def mark_failed(self, key: tuple[int, int]) -> None:
        self._set_terminal_status(key, TTSSegmentStatus.FAILED)

    def collect_timed_out_segments(self, now: float) -> list[tuple[int, int]]:
        timed_out: list[tuple[int, int]] = []
        for key, state in self.segments.items():
            if state.status in self._TERMINAL_STATUSES:
                continue
            if state.started_at is None:
                continue
            if now - state.started_at <= self._segment_total_timeout_seconds:
                continue
            state.status = TTSSegmentStatus.TIMED_OUT
            timed_out.append(key)
        return timed_out

    def _count_live_segments(self, utterance_id: int) -> int:
        return sum(
            1
            for state in self.segments.values()
            if state.utterance_id == utterance_id and state.status not in self._TERMINAL_STATUSES
        )

    def _set_terminal_status(self, key: tuple[int, int], status: TTSSegmentStatus) -> None:
        state = self.segments.get(key)
        if state is None:
            return
        if state.status == TTSSegmentStatus.TIMED_OUT and status == TTSSegmentStatus.FAILED:
            return
        state.status = status
