import json

import httpx
import pytest
from fastapi.testclient import TestClient

from governedtext2sql.api import app
from governedtext2sql.planner import Planner
from governedtext2sql.retrieval import retrieve


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv(
        "API_KEYS",
        json.dumps({"test-token": {"subject": "alice", "tenant": "north", "role": "analyst"}}),
    )
    return TestClient(app)


def test_dashboard_and_assets_are_packaged(client):
    assert client.get("/").status_code == 200
    assert "LLM + Semantic RAG" in client.get("/").text
    for path, content_type in [
        ("/static/styles.css", "text/css"),
        ("/static/app.js", "javascript"),
    ]:
        response = client.get(path)
        assert response.status_code == 200
        assert content_type in response.headers["content-type"]


def test_session_requires_auth_and_does_not_expose_secrets(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "must-never-leak")
    monkeypatch.setenv("PLANNER", "fixture")
    assert client.get("/v1/session").status_code == 401
    response = client.get("/v1/session", headers={"X-API-Key": "test-token"})
    assert response.json() == {
        "subject": "alice",
        "tenant": "north",
        "role": "analyst",
        "planner": "fixture",
        "model": None,
    }
    assert "test-token" not in response.text
    assert "must-never-leak" not in response.text


@pytest.mark.parametrize(
    "question,expected",
    [
        ("How many eligible customers?", "eligibility"),
        ("What is the conversion rate?", "conversion-rate"),
    ],
)
def test_retrieval_ranks_relevant_business_definition(question, expected):
    chunks = retrieve(question)
    assert chunks[0]["id"] == expected
    assert all(chunks[i]["score"] >= chunks[i + 1]["score"] for i in range(len(chunks) - 1))


def test_retrieved_context_reaches_live_model(monkeypatch):
    from governedtext2sql import planner

    real_client = httpx.Client
    chunks = retrieve("What is the conversion rate?")

    def handler(request):
        prompt = json.loads(request.content)["messages"][0]["content"]
        assert "Retrieved business catalog" in prompt
        assert all(chunk["text"] in prompt for chunk in chunks)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"metric":"conversion_rate"}'}}]}
        )

    monkeypatch.setenv("PLANNER", "llm")
    monkeypatch.setenv("LLM_URL", "https://model.example/v1/chat/completions")
    monkeypatch.setenv("LLM_API_KEY", "test-model-key")
    monkeypatch.setattr(
        planner.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler))
    )
    assert (
        Planner().plan("What is the conversion rate?", context=chunks).metric.value
        == "conversion_rate"
    )
