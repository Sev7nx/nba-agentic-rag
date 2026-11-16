def test_stream_emits_token_then_done(stream_client):
    with stream_client.stream(
        "POST", "/api/chat/stream", json={"question": "库里"}
    ) as response:
        body = "".join(response.iter_text())
    assert "event: token" in body
    assert "event: done" in body


def test_stream_emits_error_event_on_failure(failing_stream_client):
    with failing_stream_client.stream(
        "POST", "/api/chat/stream", json={"question": "库里"}
    ) as response:
        body = "".join(response.iter_text())
    assert "event: error" in body


def test_chat_service_stream_offloads_answer_to_thread():
    import asyncio
    import threading

    from app.models import ChatRequest, Source
    from app.services.chat_service import ChatService

    main_thread = threading.get_ident()

    class Graph:
        def __init__(self):
            self.thread_id = None

        def invoke(self, state):
            self.thread_id = threading.get_ident()
            return {
                "answer": "answer [1]",
                "sources": [
                    Source(
                        id=1,
                        title="t",
                        url="https://example.com",
                        site="x",
                        type="news",
                    )
                ],
                "trace": [],
            }

    graph = Graph()
    service = ChatService(graph)

    async def collect():
        return [
            event
            async for event in service.stream(ChatRequest(question="库里"))
        ]

    events = asyncio.run(collect())
    assert any(event.type == "token" for event in events)
    assert graph.thread_id != main_thread