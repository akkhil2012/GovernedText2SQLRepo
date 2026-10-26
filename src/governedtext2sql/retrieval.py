"""Local semantic catalog retrieval; deterministic lexical RAG, no embedding service."""

import math
import re
from collections import Counter

CATALOG = (
    {
        "id": "eligibility",
        "title": "Eligible customer",
        "text": "Eligible customers are distinct customers aged 18 or older, active, and explicitly consented. Use eligible_facts; never count contacts as customers.",
    },
    {
        "id": "conversion",
        "title": "Customer conversion",
        "text": "Conversions count distinct eligible customers with at least one subscribed contact (converted = 1), not the number of subscriptions or contacts.",
    },
    {
        "id": "conversion-rate",
        "title": "Conversion rate",
        "text": "Conversion rate is distinct converted eligible customers divided by all distinct eligible customers. Return zero for an empty denominator; repeated contacts must not change the rate.",
    },
    {
        "id": "scope",
        "title": "Governed analytics scope",
        "text": "Only aggregate metrics across all campaigns and dates are supported. Tenant comes from authenticated identity. PII, arbitrary SQL, and campaign or date filters must be refused.",
    },
)


def tokens(text: str) -> list[str]:
    return [word.rstrip("s") for word in re.findall(r"[a-z0-9]+", text.lower())]


def retrieve(question: str, limit: int = 3) -> list[dict]:
    """Rank catalog chunks using term frequency and inverse document frequency."""
    query = set(tokens(question))
    docs = [Counter(tokens(doc["title"] + " " + doc["text"])) for doc in CATALOG]
    hits = []
    for doc, counts in zip(CATALOG, docs):
        score = sum(
            (1 + math.log(counts[word]))
            * math.log(1 + len(docs) / (1 + sum(word in other for other in docs)))
            for word in query
            if counts[word]
        )
        hits.append({**doc, "score": round(score, 4)})
    return sorted(hits, key=lambda hit: (-hit["score"], hit["id"]))[:limit]
