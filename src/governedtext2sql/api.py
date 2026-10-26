import time
import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException

from .domain import Query
from .engine import Engine
from .governance import PolicyError, audit, authenticate, fingerprint

app = FastAPI(title="GovernedText2SQL", version="0.1.0")
engine = Engine()


def identity(x_api_key: str = Header(default="")):
    try:
        return authenticate(x_api_key)
    except PolicyError as exc:
        audit({"outcome": "authentication_denied", "request_id": str(uuid.uuid4())})
        raise HTTPException(401, "Unauthorized") from exc


@app.get("/health")
def health():
    return {"status": "alive"}


@app.post("/v1/query")
def query(body: Query, principal: Annotated[object, Depends(identity)]):
    start = time.perf_counter()
    request_id = str(uuid.uuid4())
    event = {
        "request_id": request_id,
        "subject": principal.subject,
        "tenant": principal.tenant,
        "mode": body.mode.value,
        "question_hash": fingerprint(body.question),
    }
    try:
        result = engine.run(body.question, body.mode, principal)
    except (ValueError, PolicyError) as exc:
        audit({**event, "outcome": "denied"})
        raise HTTPException(422, "Unsupported or disallowed analytics request") from exc
    except Exception as exc:
        audit({**event, "outcome": "execution_error"})
        raise HTTPException(503, "Analytics dependency unavailable") from exc
    elapsed = (time.perf_counter() - start) * 1000
    audit({**event, "outcome": "allowed", "latency_ms": elapsed})
    return {"request_id": request_id, "mode": body.mode, "latency_ms": elapsed, **result}
