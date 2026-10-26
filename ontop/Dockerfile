# syntax=docker/dockerfile:1
FROM python:3.11-slim AS driver
WORKDIR /download
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    python -c "import urllib.request,hashlib,pathlib; data=urllib.request.urlopen('https://repo.maven.apache.org/maven2/org/postgresql/postgresql/42.7.5/postgresql-42.7.5.jar').read(); assert hashlib.sha256(data).hexdigest() == '69020b3bd20984543e817393f2e6c01a890ef2e37a77dd11d6d8508181d079ab'; pathlib.Path('postgresql.jar').write_bytes(data)"
FROM ontop/ontop:5.3.0
COPY --from=driver /download/postgresql.jar /opt/ontop/jdbc/postgresql.jar
