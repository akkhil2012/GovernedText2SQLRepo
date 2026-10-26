# Example queries

| Natural language | Metric |
|---|---|
| How many eligible customers? | eligible_customers |
| How many conversions? | conversions |
| What is the conversion rate? | conversion_rate |

```sparql
PREFIX bank: <https://example.org/bank#>
SELECT (COUNT(DISTINCT ?customer) AS ?value) WHERE {
  ?customer a bank:MarketableCustomer ; bank:tenant "north" .
}
```

The mapping asserts EligibleCustomer, so this query needs subclass rewriting.
Equivalent semantic SQL: `SELECT COUNT(DISTINCT customer_id) AS value FROM eligible_facts`.
SQL tenant filtering is enforced through PostgreSQL RLS. SPARQL tenant filtering
is inserted from the authenticated principal by the application.

```sh
curl http://localhost:8000/v1/query \
  -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' \
  -d '{"question":"How many eligible customers?","mode":"vkg"}'
```

PII requests, custom SQL and arbitrary SPARQL are outside the public API contract.
