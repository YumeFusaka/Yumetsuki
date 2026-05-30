from ui.chat.tts_pipeline import TTSPipelineController, TTSSegmentStatus


def test_pipeline_marks_segment_cancelled_when_new_turn_begins():
    pipeline = TTSPipelineController(
        max_translation_workers=1,
        max_tts_workers=1,
        queue_limit=8,
        segment_total_timeout_seconds=10,
    )
    pipeline.begin_turn(utterance_id=1)
    pipeline.enqueue_text_segment(
        utterance_id=1,
        segment_id=0,
        text="你好。",
        needs_translation=False,
    )

    pipeline.begin_turn(utterance_id=2)

    assert pipeline.segments[(1, 0)].status == TTSSegmentStatus.CANCELLED


def test_pipeline_marks_segment_timed_out_after_total_timeout():
    pipeline = TTSPipelineController(
        max_translation_workers=1,
        max_tts_workers=1,
        queue_limit=8,
        segment_total_timeout_seconds=1,
    )
    pipeline.begin_turn(utterance_id=1)
    pipeline.enqueue_text_segment(
        utterance_id=1,
        segment_id=0,
        text="你好。",
        needs_translation=False,
    )
    pipeline.mark_synthesizing((1, 0), started_at=0.0)

    pipeline.collect_timed_out_segments(now=5.0)

    assert pipeline.segments[(1, 0)].status == TTSSegmentStatus.TIMED_OUT
