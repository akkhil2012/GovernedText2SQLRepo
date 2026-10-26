# Contributing

Use Python 3.11+ and an isolated virtual environment. Install with
`pip install -c requirements.lock -e '.[test]'`. Run Ruff and pytest as described
in the README. Integration tests must use the actual Ontop/PostgreSQL stack.

When changing metric definitions, update the independent business oracle,
semantic SQL, ontology/mappings, SPARQL compiler and documentation together.
Keep tenant policy outside model output. Do not commit secrets or real customer
data. Refresh the dependency constraints in an isolated environment and rerun
both suites when upgrading dependencies.
