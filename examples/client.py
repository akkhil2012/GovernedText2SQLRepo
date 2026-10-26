"""API_KEY=<token> python examples/client.py"""

import os

import httpx

with httpx.Client(base_url=os.getenv("API_URL", "http://localhost:8000"), timeout=40) as client:
    for mode in ("baseline", "semantic", "vkg"):
        response = client.post(
            "/v1/query",
            headers={"X-API-Key": os.environ["API_KEY"]},
            json={"question": "How many eligible customers?", "mode": mode},
        )
        response.raise_for_status()
        print(mode, response.json())
