# Security model

This reference implementation uses synthetic data and public local database
credentials. Read docs/architecture.md before shared deployment. Never expose
Ontop or PostgreSQL publicly; do not accept arbitrary model-generated SPARQL.
Treat prompts, model output and tenant identifiers as untrusted.

Report vulnerabilities privately through the repository owner's GitHub contact
or private vulnerability reporting when enabled. Do not include real customer
data or active credentials in issues, logs or proof-of-concept payloads.
