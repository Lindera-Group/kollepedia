"""Feature flags (server/app/features.py): unfinished functionality is dark
until its variable is on, and /features reports the state."""


def test_ai_is_dark_without_the_flag(client, monkeypatch):
    monkeypatch.delenv("FEATURE_AI", raising=False)
    assert client.get("/api/v1/features").json() == {"ai": False}

    draft = client.post("/api/v1/ai/draft", json={}, headers={"X-LLM-Key": "sk-ant-abc123"})
    assert draft.status_code == 404
    assert draft.json()["detail"]["code"] == "feature_disabled"

    extract = client.post("/api/v1/ai/extract", json={"text": "x"}, headers={"X-LLM-Key": "k"})
    assert extract.status_code == 404
    assert client.get("/api/v1/prompts").status_code == 404


def test_features_reports_the_flag_on(client, monkeypatch):
    monkeypatch.setenv("FEATURE_AI", "yes")
    assert client.get("/api/v1/features").json() == {"ai": True}
