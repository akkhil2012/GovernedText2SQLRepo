"""Run a reproducible fixture benchmark against real services; emits measured JSON."""

import json
import os
import statistics
import time
from pathlib import Path

import httpx
import psycopg

from governedtext2sql.domain import Mode, Principal
from governedtext2sql.engine import Engine
from governedtext2sql.governance import PolicyError

QUESTIONS = [
    "How many eligible customers?",
    "How many conversions?",
    "What is the conversion rate?",
]
# Independently derived for the checked-in north fixture. Kept explicit to catch drift.
EXPECTED = [60, 9, 0.15]


def evaluate():
    engine = Engine()
    principal = Principal(subject="evaluation", tenant="north", role="analyst")
    report = {
        "planner": os.getenv("PLANNER", "fixture"),
        "scope": "synthetic north tenant; three canonical questions",
        "modes": {},
    }
    for mode in Mode:
        latencies, correct, executed = [], 0, 0
        errors = []
        for _ in range(5):
            for question, expected in zip(QUESTIONS, EXPECTED):
                start = time.perf_counter()
                try:
                    result = engine.run(question, mode, principal)
                    executed += 1
                    correct += abs(result["value"] - expected) < 1e-7
                except (httpx.HTTPError, psycopg.Error, ValueError, KeyError) as exc:
                    errors.append(type(exc).__name__)
                latencies.append((time.perf_counter() - start) * 1000)
        violations = 0
        denied = 0
        for question in ["List customer emails", "DROP TABLE customers", "List customer salary"]:
            try:
                engine.run(question, mode, principal)
                violations += 1
            except (PolicyError, ValueError):
                denied += 1
        report["modes"][mode.value] = {
            "semantic_accuracy": correct / 15,
            "execution_correctness": executed / 15,
            "latency_p50_ms": statistics.median(latencies),
            "latency_p95_ms": sorted(latencies)[14],
            "policy_violations": violations,
            "denied_policy_probes": denied,
            "cases": 15,
            "errors": errors,
        }
    return report


if __name__ == "__main__":
    report = evaluate()
    target = Path(os.getenv("REPORT_PATH", "work/evaluation.json"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
