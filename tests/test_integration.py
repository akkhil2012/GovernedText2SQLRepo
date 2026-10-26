"""Real PostgreSQL + Ontop tests; no mocks or alternate query engine."""

import os

import psycopg
import pytest

from governedtext2sql.domain import Mode, Principal
from governedtext2sql.engine import Engine

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION") != "1", reason="Set RUN_INTEGRATION=1 with stack running"
    ),
]


def golden(tenant):
    # Independent business oracle over deterministic source records, not generated SQL.
    ids = range(1, 101) if tenant == "north" else range(101, 201)
    eligible = {n for n in ids if n % 10 != 0 and n % 7 != 0 and n % 4 != 0}
    converted = {n for n in eligible if any(k % 5 == 0 for k in (n, n + 200, n + 400))}
    return [len(eligible), len(converted), len(converted) / len(eligible)]


@pytest.mark.parametrize("tenant", ["north", "south"])
@pytest.mark.parametrize("mode", [Mode.semantic, Mode.vkg])
def test_semantics_and_ontology_inference(tenant, mode):
    engine = Engine()
    principal = Principal(subject="test", tenant=tenant, role="analyst")
    for question, expected in zip(
        ["How many eligible customers?", "How many conversions?", "What is the conversion rate?"],
        golden(tenant),
    ):
        assert engine.run(question, mode, principal)["value"] == pytest.approx(expected)


def test_rls_and_pii():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute("SELECT set_config('app.tenant','north',true)")
        assert conn.execute("SELECT DISTINCT tenant FROM campaign_facts").fetchall() == [("north",)]
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT email FROM customers")


def test_missing_tenant_fails_closed():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM campaign_facts").fetchone()[0] == 0


def test_baseline_is_executable_but_semantically_wrong():
    p = Principal(subject="test", tenant="north", role="analyst")
    assert (
        Engine().run("How many eligible customers?", Mode.baseline, p)["value"]
        != golden("north")[0]
    )


@pytest.mark.parametrize("mode", [Mode.baseline, Mode.semantic, Mode.vkg])
def test_empty_tenant(mode):
    principal = Principal(subject="test", tenant="empty", role="analyst")
    for question in [
        "How many eligible customers?",
        "How many conversions?",
        "What is the conversion rate?",
    ]:
        assert Engine().run(question, mode, principal)["value"] == 0


def test_contact_rls():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute("SELECT set_config('app.tenant','north',true)")
        assert (
            conn.execute("SELECT COUNT(*) FROM contacts WHERE customer_id > 100").fetchone()[0] == 0
        )
