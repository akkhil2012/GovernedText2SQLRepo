-- Synthetic demo only. Replace local credentials before any shared deployment.
CREATE ROLE analytics LOGIN PASSWORD 'analytics_demo';
CREATE ROLE ontop_reader LOGIN PASSWORD 'ontop_demo';
CREATE TABLE customers (
 id integer PRIMARY KEY, tenant text NOT NULL, age integer NOT NULL CHECK(age >= 0),
 active boolean NOT NULL, consent boolean NOT NULL, segment text NOT NULL,
 email text NOT NULL
);
CREATE TABLE contacts (
 id integer PRIMARY KEY, customer_id integer NOT NULL REFERENCES customers(id),
 campaign text NOT NULL, channel text NOT NULL, contacted_on date NOT NULL,
 subscribed boolean NOT NULL
);
INSERT INTO customers
SELECT n, CASE WHEN n <= 100 THEN 'north' ELSE 'south' END,
  CASE WHEN n % 10 = 0 THEN 17 ELSE 25 + n % 50 END,
  n % 7 <> 0, n % 4 <> 0,
  CASE WHEN n % 2 = 0 THEN 'retail' ELSE 'affluent' END,
  'synthetic-' || n || '@example.invalid'
FROM generate_series(1,200) n;
INSERT INTO contacts
SELECT n, (n-1)%200+1, CASE WHEN n%2=0 THEN 'term-deposit' ELSE 'savings' END,
 CASE WHEN n%3=0 THEN 'phone' ELSE 'email' END,
 DATE '2026-01-01' + n%90, n%5=0
FROM generate_series(1,600) n;
-- A small adversarial fixture: repeated contacts and subscriptions among ineligible people.
CREATE VIEW campaign_facts WITH (security_invoker=true) AS
SELECT c.tenant, c.id AS customer_id, t.id AS contact_id,
 CASE WHEN c.age>=18 AND c.active AND c.consent THEN 1 ELSE 0 END AS eligible,
 CASE WHEN t.subscribed THEN 1 ELSE 0 END AS converted
FROM customers c LEFT JOIN contacts t ON t.customer_id=c.id;
CREATE VIEW eligible_facts WITH (security_invoker=true) AS
SELECT * FROM campaign_facts WHERE eligible=1;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers FORCE ROW LEVEL SECURITY;
CREATE POLICY analytics_tenant ON customers TO analytics
 USING (tenant = current_setting('app.tenant', true));
CREATE POLICY ontop_all ON customers TO ontop_reader USING (true);
GRANT USAGE ON SCHEMA public TO analytics, ontop_reader;
-- Column grants prevent raw PII reads even through SQL injection.
GRANT SELECT(id,tenant,age,active,consent) ON customers TO analytics, ontop_reader;
GRANT SELECT ON contacts, campaign_facts, eligible_facts TO analytics, ontop_reader;
ALTER ROLE analytics SET default_transaction_read_only = on;
ALTER ROLE ontop_reader SET default_transaction_read_only = on;
ALTER ROLE ontop_reader SET statement_timeout = '5s';
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts FORCE ROW LEVEL SECURITY;
CREATE POLICY contact_tenant ON contacts TO analytics USING (
 EXISTS (SELECT 1 FROM customers c WHERE c.id=contacts.customer_id)
);
CREATE POLICY ontop_contacts ON contacts TO ontop_reader USING (true);
