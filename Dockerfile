# syntax=docker/dockerfile:1
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY src ./src
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then PIP_CERT=/run/secrets/proxy_ca pip install --no-cache-dir -c requirements.lock .; else pip install --no-cache-dir -c requirements.lock .; fi
RUN useradd --uid 10001 --create-home app && mkdir /app/audit && chown app /app/audit
USER 10001
ENV AUDIT_PATH=/app/audit/events.jsonl
EXPOSE 8000
CMD ["uvicorn", "governedtext2sql.api:app", "--host", "0.0.0.0", "--port", "8000"]
