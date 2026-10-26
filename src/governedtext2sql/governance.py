"""Deny by default SQL grammar: one scalar aggregate over one governed relation."""

import hashlib
import hmac
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import sqlglot
from sqlglot import exp

from .domain import Principal


class PolicyError(ValueError):
    pass


def authenticate(key: str) -> Principal:
    # Keys are configured server-side. Never accept roles or tenants from request headers.
    records = json.loads(os.environ.get("API_KEYS", "{}"))
    for token, identity in records.items():
        if hmac.compare_digest(key, token):
            principal = Principal.model_validate(identity)
            if principal.role not in {"analyst", "auditor"}:
                raise PolicyError("Role cannot query analytics")
            return principal
    raise PolicyError("Invalid API key")


def validate_sql(sql: str) -> str:
    try:
        statements = sqlglot.parse(sql, read="postgres")
    except sqlglot.errors.ParseError as exc:
        raise PolicyError("Invalid SQL") from exc
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise PolicyError("Exactly one SELECT is required")
    tree = statements[0]
    allowed = {
        exp.Select,
        exp.From,
        exp.Table,
        exp.Identifier,
        exp.Column,
        exp.Alias,
        exp.Count,
        exp.Sum,
        exp.Avg,
        exp.Star,
        exp.Distinct,
        exp.Literal,
        exp.Mul,
        exp.Div,
        exp.Add,
        exp.Sub,
        exp.Paren,
    }
    if any(type(node) not in allowed for node in tree.walk()):
        raise PolicyError("SQL construct is outside the analytics grammar")
    tables = list(tree.find_all(exp.Table))
    if len(tables) != 1 or tables[0].name != "campaign_facts" or tables[0].db:
        raise PolicyError("Only campaign_facts is permitted")
    if len(tree.expressions) != 1 or not isinstance(tree.expressions[0], exp.Alias):
        raise PolicyError("One aggregate aliased as value is required")
    expr = tree.expressions[0]
    if expr.alias != "value" or not isinstance(expr.this, (exp.Count, exp.Sum, exp.Avg)):
        raise PolicyError("One scalar aggregate is required")
    if any(
        c.name not in {"customer_id", "eligible", "converted", "contact_id"}
        for c in tree.find_all(exp.Column)
    ):
        raise PolicyError("Column is not permitted")
    return tree.sql(dialect="postgres")


def audit(event: dict) -> None:
    # Append before responding; failures fail the request closed. No question, key or result stored.
    path = Path(os.getenv("AUDIT_PATH", "work/audit.jsonl"))
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"time": datetime.now(UTC).isoformat(), **event}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")


def fingerprint(question: str) -> str:
    return hashlib.sha256(question.encode()).hexdigest()
