import requests
from tts.adapter import TTSAdapter
from config.schema import TTSConfig


class GPTSoVITSAdapter(TTSAdapter):
    def __init__(self, config: TTSConfig):
        self._api_url = config.api_url

    def synthesize(self, text: str) -> bytes | None:
        try:
            resp = requests.post(
                self._api_url,
                json={"text": text, "text_language": "zh"},
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.content
            return None
        except Exception:
            return None
