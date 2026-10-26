"""Bounded Ontop readiness check, including ontology/mapping initialization."""

import os
import time

import httpx

for attempt in range(60):
    try:
        r = httpx.post(
            os.getenv("ONTOP_URL", "http://localhost:8089/sparql"),
            data={"query": "ASK { ?s ?p ?o }"},
            headers={"Accept": "application/sparql-results+json"},
            timeout=3,
            trust_env=False,
        )
        r.raise_for_status()
        assert r.json()["boolean"] is True
        break
    except (httpx.HTTPError, ValueError, KeyError, AssertionError):
        if attempt == 59:
            raise
        time.sleep(2)
