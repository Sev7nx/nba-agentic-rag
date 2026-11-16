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