# GovernedText2SQL

A production-style reference repository comparing baseline LLM SQL, a curated
semantic layer, and an ontology-driven Virtual Knowledge Graph powered by Ontop.
Python 3.11+, FastAPI, PostgreSQL 16, OWL/RDF, R2RML, SPARQL, Compose and pytest.
All banking data is synthetic. This is an executable demonstration with explicit
production hardening boundaries, not a banking-ready service.

## Quick start

```sh
cp .env.example .env
# Edit .env: replace the API token. API_KEYS is a JSON map of token to identity.
docker compose up --build -d
# Wait for Ontop initialization; /health is process liveness only.
export API_KEY=replace-with-a-long-random-token
python -m venv .venv
. .venv/bin/activate
pip install -c requirements.lock -e '.[test]'
python examples/client.py
```

API docs: http://localhost:8000/docs. API binds to localhost. Database and Ontop
are private by default. `POST /v1/query` accepts question and mode (baseline,
semantic, vkg); returns scalar value, generated query, language, request ID and
latency. Authentication uses X-API-Key and server-assigned subject/tenant/role.
GET /health is public process liveness. Invalid keys return 401, unsupported or
unsafe plans 422, dependency errors 503. Auditor and analyst roles both have
aggregate access; no role can retrieve PII through this API.

Fixture mode needs no external model and deliberately demonstrates baseline
semantic errors. To use a real LLM set PLANNER=llm and LLM_URL, LLM_API_KEY,
LLM_MODEL in .env. LLM_URL must be an OpenAI-compatible chat completion endpoint.
Model output is treated as untrusted. The ontology path uses a constrained metric
plan compiled to SPARQL, rather than accepting arbitrary model-generated SPARQL.

## Test and evaluate

```sh
pytest -m 'not integration' -q
ruff check src tests examples
docker compose -f compose.yaml -f compose.test.yaml up -d
python examples/wait_ready.py
export DATABASE_URL=postgresql://analytics:analytics_demo@localhost:54329/banking
export ONTOP_URL=http://localhost:8089/sparql
RUN_INTEGRATION=1 pytest -q
python examples/evaluate.py
```

The test override exposes dependency ports on localhost only. Never enable it on
a shared host. CI runs unit and real Ontop/PostgreSQL integration suites and
uploads the measured evaluation JSON. Reports distinguish semantic accuracy from
successful SQL execution and include latency and policy-probe outcomes.
See [evaluation protocol](docs/evaluation.md) for limits and fair interpretation.

## Repository guide

- `src/governedtext2sql/`: planners, compilers, execution, governance and REST API
- `db/`: schema, deterministic banking fixture, RLS and least-privilege roles
- `ontop/`: OWL ontology, R2RML mappings and JDBC properties
- `tests/`: unit/security and real-service integration checks
- `examples/`: API client, readiness check and benchmark
- [Architecture and governance](docs/architecture.md)
- [Queries and business definitions](docs/queries.md)

`docker compose down` preserves data and audit volumes. To reset the synthetic
database, explicitly run `docker compose down -v` (deletes all demo data and logs).
Database initialization runs only on the first empty volume. After schema changes
use a fresh demo volume; production deployments need managed migrations.

## Deployment boundaries

Use new secrets, TLS, per-tenant Ontop/database isolation where required,
external durable audit storage, gateway quotas and image digest pinning before
shared deployment. Never publish Ontop directly: its service account can read
all tenants' non-PII facts. See the trust model in the architecture document.
Licensed under MIT.
