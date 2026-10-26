# Evaluation protocol

Run `python examples/evaluate.py` against PostgreSQL and Ontop to create
`work/evaluation.json`. Run integration tests first. The harness executes three
canonical questions five times for each mode and records result-based semantic
accuracy, successful-execution fraction, median and nearest-rank p95 wall latency,
and three explicit policy probes. Dependency errors count as failed executions.
The test suite separately checks RLS, missing-tenant denial, PII privileges,
SQL attacks and API authentication/audit behavior.

Default fixture planning is deterministic and deliberately uses common baseline
mistakes: counting contacts rather than distinct eligible customers and using
contact averages for customer conversion rate. It is a demonstration, not measured
LLM performance or a claim that every LLM produces these errors. To benchmark an
actual LLM, set PLANNER=llm, configure endpoint/key/model, retain raw private traces
under your own governance controls, broaden the human-reviewed corpus and repeat
runs. Both semantic and VKG paths share metric definitions and may achieve equal
accuracy; ontology support is independently tested by subclass inference.

The three policy probes are a small regression set, not a security certification.
Zero violations on them does not prove absence of vulnerabilities. Latency
includes planning, connection creation, network and execution; it does not isolate
Ontop translation time. Current cases have no campaign/date filters. Unsupported
requests fail closed in fixture mode; LLM mode must be assessed for intent drift.

## Observed local run (2026-10-26)

33 pytest checks passed against real PostgreSQL 16.6 and Ontop 5.3.0; lint passed.
Python host: 3.12; API container: 3.11. The example client completed all modes.
A Starlette TestClient deprecation warning remains in the pinned dependency set.

| Mode | Result accuracy | Executed | p50 ms | p95 ms | Policy violations |
|---|---:|---:|---:|---:|---:|
| Baseline fixture | 0% | 100% | 10.03 | 16.79 | 0/3 |
| Semantic fixture | 100% | 100% | 15.08 | 19.77 | 0/3 |
| VKG fixture | 100% | 100% | 384.77 | 408.03 | 0/3 |

Raw measured results: [evaluation-sample.json](evaluation-sample.json). These are
fixture results on a tiny synthetic corpus. They demonstrate the engineered
semantic differences, not general model quality or an inherent VKG advantage over
a correctly implemented semantic layer. No live model credentials were available;
the HTTP adapter was verified with a mock transport. Live LLM benchmarking remains
an operator task.
