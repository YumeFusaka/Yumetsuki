from llm.text_processor import TextProcessor


def test_text_processor_strips_emotion_tag_with_punctuation_payload():
    processed = TextProcessor().process("[emotion:超やばい！]こんにちは！")

    assert processed.emotion == "超やばい！"
    assert processed.clean_text == "こんにちは！"
