from memory.mem0_store import Mem0MemoryStore


class FakeMemoryClient:
    def __init__(self):
        self.add_calls = []
        self.search_calls = []

    def add(self, messages, user_id):
        self.add_calls.append({"messages": messages, "user_id": user_id})

    def search(self, query, filters, limit=None):
        self.search_calls.append({"query": query, "filters": filters, "limit": limit})
        return {
            "results": [
                {"memory": "用户喜欢樱花主题", "score": 0.91},
                {"memory": "用户希望桌宠响应快", "score": 0.88},
            ]
        }


def test_mem0_store_searches_with_user_filter():
    client = FakeMemoryClient()
    store = Mem0MemoryStore(memory_client=client)

    memories = store.search_relevant("我喜欢什么主题？", user_id="u1")

    assert memories == ["用户喜欢樱花主题", "用户希望桌宠响应快"]
    assert client.search_calls == [{
        "query": "我喜欢什么主题？",
        "filters": {"user_id": "u1"},
        "limit": None,
    }]


def test_mem0_store_adds_conversation_messages():
    client = FakeMemoryClient()
    store = Mem0MemoryStore(memory_client=client)

    store.add_conversation("你好", "你好呀", user_id="u1")

    assert client.add_calls == [{
        "messages": [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好呀"},
        ],
        "user_id": "u1",
    }]


def test_mem0_store_respects_top_k_limit():
    client = FakeMemoryClient()
    store = Mem0MemoryStore(memory_client=client, top_k=1)

    memories = store.search_relevant("保留几条？", user_id="u1")

    assert memories == ["用户喜欢樱花主题", "用户希望桌宠响应快"]
    assert client.search_calls == [{
        "query": "保留几条？",
        "filters": {"user_id": "u1"},
        "limit": 1,
    }]
