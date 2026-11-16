def test_e2e_question_to_answer(client):
    response = client.post("/api/chat", json={"question": "库里最经典的比赛"})
    assert response.status_code == 200
    assert response.json()["answer"]
    assert response.json()["sources"] is not None