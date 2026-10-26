"""Only VKG calls Ontop; there is no local SPARQL-to-SQL substitute."""

import os
import re
import time

import httpx
import psycopg

from .domain import Metric, Mode
from .governance import PolicyError, validate_sql
from .planner import Planner
from .retrieval import retrieve

SQL = {
    Metric.eligible_customers: "SELECT COUNT(DISTINCT customer_id) AS value FROM eligible_facts",
    Metric.conversions: "SELECT COUNT(DISTINCT customer_id) AS value FROM eligible_facts WHERE converted = 1",
    Metric.conversion_rate: """SELECT COALESCE(1.0 * COUNT(DISTINCT CASE WHEN converted = 1
        THEN customer_id END) / NULLIF(COUNT(DISTINCT customer_id), 0), 0) AS value
        FROM eligible_facts""",
}


def sparql(metric: Metric, tenant: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", tenant):
        raise PolicyError("Invalid tenant configuration")
    aggregate = {
        Metric.eligible_customers: "COUNT(DISTINCT ?customer)",
        Metric.conversions: "COUNT(DISTINCT ?convertedCustomer)",
        Metric.conversion_rate: "IF(COUNT(DISTINCT ?customer)=0, 0, 1.0 * COUNT(DISTINCT ?convertedCustomer) / COUNT(DISTINCT ?customer))",
    }[metric]
    return f'''PREFIX bank: <https://example.org/bank#>
SELECT ({aggregate} AS ?value) WHERE {{
 ?customer a bank:MarketableCustomer ; bank:tenant "{tenant}" .
 OPTIONAL {{ ?customer bank:hasConversion ?conversion . BIND(?customer AS ?convertedCustomer) }}
}}'''


class Engine:
    def __init__(self, planner=None):
        self.planner = planner or Planner()

    def run(self, question, mode, principal):
        stages = []
        context = []
        metric = None

        def record(name, started, detail):
            stages.append(
                {
                    "name": name,
                    "latency_ms": (time.perf_counter() - started) * 1000,
                    "detail": detail,
                }
            )

        if mode == Mode.semantic:
            started = time.perf_counter()
            context = retrieve(question)
            record(
                "Retrieve semantic context",
                started,
                "Ranked local business catalog using lexical TF-IDF retrieval.",
            )
        started = time.perf_counter()
        if mode == Mode.baseline:
            generated = self.planner.complete(question, baseline=True)
            record(
                "Generate SQL",
                started,
                "Planner receives the physical schema without semantic retrieval.",
            )
            started = time.perf_counter()
            query = validate_sql(generated)
            record(
                "Validate SQL policy",
                started,
                "AST allowlist: one scalar aggregate on campaign_facts.",
            )
        else:
            plan = (
                self.planner.plan(question, context=context)
                if mode == Mode.semantic
                else self.planner.plan(question)
            )
            metric = plan.metric.value
            record(
                "Generate typed metric plan",
                started,
                "Validated enum plan; models cannot provide SQL, tenants or policy.",
            )
            started = time.perf_counter()
            query = sparql(plan.metric, principal.tenant) if mode == Mode.vkg else SQL[plan.metric]
            record(
                "Compile governed SPARQL" if mode == Mode.vkg else "Compile semantic SQL",
                started,
                "Inject authenticated tenant; query MarketableCustomer via OWL subclass inference."
                if mode == Mode.vkg
                else "Compile a reviewed customer-level metric definition.",
            )
        started = time.perf_counter()
        if mode == Mode.vkg:
            with httpx.Client(timeout=10, trust_env=False) as client:
                response = client.post(
                    os.getenv("ONTOP_URL", "http://localhost:8080/sparql"),
                    data={"query": query},
                    headers={"Accept": "application/sparql-results+json"},
                )
                response.raise_for_status()
                rows = response.json()["results"]["bindings"]
                value = float(rows[0]["value"]["value"])
        else:
            with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                conn.execute("SELECT set_config('app.tenant', %s, true)", (principal.tenant,))
                conn.execute("SET LOCAL statement_timeout = '5s'")
                value = float(conn.execute(query).fetchone()[0] or 0)
        record(
            "Ontop rewrite + database execution" if mode == Mode.vkg else "PostgreSQL execution",
            started,
            "Ontop performs OWL rewriting, R2RML unfolding and SQL execution."
            if mode == Mode.vkg
            else "Read-only transaction, tenant RLS and five-second statement timeout.",
        )
        return {
            "value": value,
            "query": query,
            "language": "sparql" if mode == Mode.vkg else "sql",
            "metric": metric,
            "planner": os.getenv("PLANNER", "fixture"),
            "stages": stages,
            "retrieved_context": context,
            "governance": "Aggregate-only access; authenticated tenant; API records audit before responding.",
        }
