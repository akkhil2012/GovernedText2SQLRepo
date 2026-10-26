import json

import pytest
from fastapi.testclient import TestClient

from governedtext2sql.api import app
from governedtext2sql.domain import Metric
from governedtext2sql.engine import sparql
from governedtext2sql.governance import PolicyError, authenticate, validate_sql
from governedtext2sql.planner import Planner


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM customers",
        "SELECT COUNT(*) AS value FROM customers",
        "SELECT email AS value FROM campaign_facts",
        "SELECT pg_sleep(9) AS value FROM campaign_facts",
        "SELECT COUNT(*) AS value FROM campaign_facts; DROP TABLE customers",
        "SELECT COUNT(*) AS value FROM campaign_facts WHERE tenant='south'",
        "SELECT COUNT(*) AS value FROM public.campaign_facts",
        "SELECT COUNT(*) AS value FROM campaign_facts UNION SELECT 1",
        "SELECT COUNT(*) AS value INTO stolen FROM campaign_facts",
        "SELECT COUNT(*) AS value FROM campaign_facts JOIN customers ON true",
        "WITH x AS (DELETE FROM customers) SELECT COUNT(*) AS value FROM campaign_facts",
        "SELECT COUNT(email) AS value FROM campaign_facts",
    ],
)
def test_sql_rejects_unsafe(sql):
    with pytest.raises(PolicyError):
        validate_sql(sql)


@pytest.mark.parametrize(
    "question",
    ["How many eligible customers?", "How many conversions?", "What is the conversion rate?"],
)
def test_fixture_baseline_passes_safety(question):
    validate_sql(Planner().complete(question, baseline=True))


def test_tenant_injection_rejected():
    with pytest.raises(PolicyError):
        sparql(Metric.conversions, 'north" . } UNION { ?s ?p ?o')


def test_authentication(monkeypatch):
    monkeypatch.setenv(
        "API_KEYS", json.dumps({"secret": {"subject": "a", "tenant": "north", "role": "analyst"}})
    )
    assert authenticate("secret").tenant == "north"
    with pytest.raises(PolicyError):
        authenticate("bad")


def test_api_audit_and_errors(monkeypatch, tmp_path):
    from governedtext2sql import api

    monkeypatch.setenv("AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv(
        "API_KEYS", json.dumps({"secret": {"subject": "a", "tenant": "north", "role": "analyst"}})
    )
    client = TestClient(app)
    assert client.post("/v1/query", json={"question": "List customer emails"}).status_code == 401
    assert (
        client.post(
            "/v1/query", headers={"X-API-Key": "secret"}, json={"question": "List customer emails"}
        ).status_code
        == 422
    )
    monkeypatch.setattr(api.engine, "run", lambda *args: {"value": 3})
    response = client.post(
        "/v1/query",
        headers={"X-API-Key": "secret"},
        json={"question": "How many eligible customers?"},
    )
    assert response.status_code == 200
    assert response.json()["latency_ms"] >= 0
    records = [json.loads(x) for x in (tmp_path / "audit.jsonl").read_text().splitlines()]
    assert [x["outcome"] for x in records] == ["authentication_denied", "denied", "allowed"]
    assert "secret" not in (tmp_path / "audit.jsonl").read_text()
    assert "emails" not in (tmp_path / "audit.jsonl").read_text()


def test_model_plan_cannot_supply_sql(monkeypatch):
    planner = Planner()
    monkeypatch.setattr(
        planner, "complete", lambda q: '{"metric":"conversions", "sql":"DROP TABLE customers"}'
    )
    with pytest.raises(ValueError):
        planner.plan("count conversions")


def test_ontology_and_mapping_parse():
    from rdflib import Graph

    assert len(Graph().parse("ontop/ontology.ttl")) > 10
    assert len(Graph().parse("ontop/mapping.ttl")) > 10


def test_llm_adapter(monkeypatch):
    import httpx

    from governedtext2sql import planner as module

    real_client = httpx.Client

    def handler(request):
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        assert request.headers["Authorization"] == "Bearer test-key"
        content = (
            "SELECT COUNT(*) AS value FROM campaign_facts"
            if "SQL only" in payload["messages"][0]["content"]
            else '{"metric":"conversions"}'
        )
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    monkeypatch.setenv("PLANNER", "llm")
    monkeypatch.setenv("LLM_URL", "https://model.example/v1/chat/completions")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setattr(
        module.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler))
    )
    assert Planner().plan("How many conversions?").metric == Metric.conversions
    validate_sql(Planner().complete("How many conversions?", baseline=True))


def test_unsupported_filter_is_not_silently_ignored():
    with pytest.raises(ValueError):
        Planner().plan("How many eligible customers last month?")
