from llm.text_processor import TextProcessor


def test_extract_emotion():
    tp = TextProcessor()
    text = "[emotion:happy]你好呀！很高兴见到你~"
    result = tp.process(text)
    assert result.emotion == "happy"
    assert result.clean_text == "你好呀！很高兴见到你~"


def test_no_emotion():
    tp = TextProcessor()
    text = "今天天气真好"
    result = tp.process(text)
    assert result.emotion is None
    assert result.clean_text == "今天天气真好"


def test_multiple_emotions_takes_first():
    tp = TextProcessor()
    text = "[emotion:sad]唉...[emotion:angry]真是的！"
    result = tp.process(text)
    assert result.emotion == "sad"
    assert result.clean_text == "唉...真是的！"


def test_emotion_mid_text():
    tp = TextProcessor()
    text = "嗯...[emotion:shy]那个...人家..."
    result = tp.process(text)
    assert result.emotion == "shy"
    assert result.clean_text == "嗯...那个...人家..."
