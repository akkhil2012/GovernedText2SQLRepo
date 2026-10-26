# Architecture and trust boundaries

```mermaid
flowchart LR
  U[Query Studio / API client] --> A[FastAPI authentication + tenant + audit]
  A --> B[Baseline LLM: SQL]
  A --> S[Semantic LLM: typed metric]
  A --> V[VKG LLM: typed metric]
  B --> G[SQL AST allowlist]
  G --> P[PostgreSQL + tenant RLS]
  S --> C[Reviewed metric SQL]
  C --> P
  V --> Q[Reviewed SPARQL compiler + tenant constraint]
  Q --> O[Ontop + OWL + R2RML]
  O --> P
```

Models are untrusted. Baseline output is restricted to a scalar COUNT/SUM/AVG
on the non-PII campaign_facts relation. Every request uses a server-configured
identity; request bodies cannot choose a role or tenant. SQL transactions set
app.tenant locally, are read-only, and have a five-second statement timeout.
PostgreSQL security-invoker views preserve caller RLS and column privileges.
A baseline may be semantically incorrect while remaining policy compliant.

Semantic RAG mode retrieves the top three business-definition chunks from a
local catalog using lexical term frequency/inverse document frequency ranking.
Retrieved chunks augment the live LLM prompt; the returned enum metric compiles
to reviewed SQL. Fixture mode demonstrates the same retrieval trace while using
deterministic planning. This implementation does not use vector embeddings. VKG mode selects
the same enum, compiles SPARQL and sends it to the actual Ontop endpoint. Ontop
performs ontology rewriting and SQL unfolding; the application does not emulate
this step. EligibleCustomer is a subclass of MarketableCustomer. Mappings assert
only EligibleCustomer; queries request MarketableCustomer, exercising subclass
inference. Age, active status and consent are grounded in the SQL-backed mapping,
not inferred from absent RDF facts. OWL open-world reasoning is not consent policy.

The Ontop service account can read all tenants' non-PII facts. Tenant isolation on
this path relies on the server's closed SPARQL compiler. Ontop and PostgreSQL are
private Compose services and must not be exposed outside the trusted network.
Never add an arbitrary SPARQL endpoint or forward model-produced SPARQL without
additional authorization. For stronger isolation deploy separate Ontop instances
and database roles per tenant. Ontology reasoning itself does not enforce access.

## Semantics

Eligible customers: distinct adult (age >= 18), active, consented customers.
Conversions: distinct eligible customers with at least one subscribed contact.
Conversion rate: conversions / eligible customers; empty populations return zero.
The fixture spans two tenants, 200 customers, 600 contacts, multiple campaigns,
channels, dates and segments, including minors, opt-outs, inactive customers and
repeated contact. Current supported metrics span all dates and campaigns; campaign
or date filtering is not yet supported and should not be inferred from questions.

## Operations

JSONL audit records contain subject, tenant, mode, request ID, question hash,
outcome and successful execution latency. Questions, tokens and query results are
not stored. An audit write failure prevents successful responses. Local append
logs are not tamper-proof; production requires an external durable audit sink,
retention controls, rotation and restricted access. Failed authentication and
policy failures are logged. FastAPI schema validation failures use its default
422 handler and are not part of the query audit stream.

Health reports process liveness; dependency failures return 503. Requests have
bounded input, model/HTTP/database timeouts and scalar output. Add TLS, a secret
manager, gateway rate limiting, centralized observability, model evaluation,
image digest pinning and organization-specific authorization before production.
Local database passwords are intentionally public demo credentials on synthetic
data. Never reuse them with real banking records.

## Query Studio

FastAPI serves the buildless dashboard at `/` with packaged assets at `/static`.
`GET /v1/session` authenticates the API key and returns subject, tenant, role,
planner type and model name, never credentials or model endpoint configuration.
The browser stores its key only in memory, never localStorage or sessionStorage.
Every comparison invokes the existing audited `/v1/query` endpoint separately
for each mode. One failure does not discard successful results from other modes.

Query responses include planner type, metric (when a typed plan is used), retrieved
context, and measured stage names/durations/details. These are observable process
steps, not hidden model reasoning. Stage durations include local/network/connection
overhead. Ontop rewriting and SQL execution remain a single combined stage;
there is no claim to separately measure translation or expose its internal SQL.
Total request latency is measured by the API. Result agreement and fastest-this-run
labels are comparisons, not ground-truth accuracy or statistically sound benchmarks.
JSON exports omit API keys. The application ships no third-party scripts or fonts.
