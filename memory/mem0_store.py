from __future__ import annotations

from pathlib import Path

class Mem0MemoryStore:
    def __init__(self, memory_client, top_k: int | None = None):
        self._memory_client = memory_client
        self._top_k = top_k

    def search_relevant(self, query: str, user_id: str) -> list[str]:
        result = self._memory_client.search(query, filters={"user_id": user_id}, limit=self._top_k)
        memories = result.get("results", []) if isinstance(result, dict) else []
        return [item.get("memory", "") for item in memories if item.get("memory")]

    def add_conversation(self, user_text: str, assistant_text: str, user_id: str) -> None:
        messages = [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": assistant_text},
        ]
        self._memory_client.add(messages, user_id=user_id)


def build_local_mem0_store(config):
    from mem0 import Memory

    storage_dir = Path(config.storage_dir).expanduser()
    storage_dir.mkdir(parents=True, exist_ok=True)
    chroma_dir = storage_dir / "chroma"
    chroma_dir.mkdir(parents=True, exist_ok=True)
    history_db_path = storage_dir / "history.db"

    memory = Memory.from_config({
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": "yumetsuki",
                "path": str(chroma_dir),
            },
        },
        "llm": {
            "provider": "openai",
            "config": {},
        },
        "embedder": {
            "provider": "openai",
            "config": {},
        },
        "history_db_path": str(history_db_path),
    })
    return Mem0MemoryStore(memory_client=memory, top_k=config.top_k)
