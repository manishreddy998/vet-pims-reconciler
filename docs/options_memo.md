# Memo: where the warehouse should live for the next 12 months

**Question.** Should a wellness-plan company with one Postgres app database, a dbt warehouse, and hundreds of millions of PIMS rows move to a cloud warehouse now?

**Recommendation.** Not yet. Keep Postgres and dbt, give analytics its own database, make the big models incremental, and set clear triggers for when to move. Spend the first quarter on definitions, not infrastructure. That is where the trust problem is.

## Options

| | A. Postgres + dbt, analytics split out | B. Cloud warehouse (Snowflake, BigQuery, Redshift Serverless) | C. DuckDB / MotherDuck for analytics |
|---|---|---|---|
| What changes | Analytics moves to its own Postgres database or read replica. Nightly full rebuild becomes incremental models. | New warehouse, new loaders, dbt adapter switch, BI and AI tools repointed. | Analytics runs on DuckDB files or MotherDuck, fed from Postgres. |
| Effort | 2 to 4 weeks, mostly dbt work | 6 to 10 weeks including validation and cutover | 2 to 3 weeks |
| Run cost (rough, list prices) | Low hundreds of dollars a month for one more managed Postgres instance | Usage-based. Low thousands a month is typical once BI and scheduled jobs run daily | Lowest. Free locally, modest on MotherDuck |
| Good at | Same SQL and skills the team already has. App data and analytics stay one hop apart. | Scales without tuning. Separates heavy queries from each other. Strong governance features. | Very fast scans on a single machine. Great for an analyst laptop and CI. |
| Weak at | Large scans get slow without partitioning and good indexes. Concurrency is limited. | Another vendor, another bill to watch, migration risk while definitions are still moving. | Many concurrent BI users. Fewer governance features. |

## Why A first

1. **The pain is meaning, not speed.** "Appointment" and "invoice" mean different things in each PIMS. A faster engine returns the wrong number faster. This project shows the fix: one system of record per clinic per date, one status vocabulary, one money definition, and tests that fail when a rule breaks.
2. **Postgres handles this size** with incremental models, date partitioning on the big fact tables, and indexes on the join keys (`golden_patient_id`, `clinic_id`, `local_date`).
3. **The dbt project is portable.** Everything here runs on DuckDB and Postgres from the same SQL (see `macros/portable.sql`). If the triggers below fire, moving to B is an adapter change plus loaders, not a rewrite.

## Move to B when any of these is true

- The nightly rebuild takes more than about 2 hours even after going incremental.
- More than about 5 people run heavy queries at the same time and the app database feels it.
- Event or clickstream data arrives in the billions of rows.
- A customer or partner needs governed data sharing.

## First 90 days

| Weeks | Work | Done when |
|---|---|---|
| 1 to 2 | Map the data landscape: every source, table, owner, refresh time, and which copy is canonical. Talk to GTM, CX, finance and product. | One page anyone can read. No more tribal knowledge. |
| 3 to 6 | Conformed `appointment`, `invoice`, `patient` and `membership` models with matching rules and tests, like this repo. | Finance, CX and product get the same visit count. |
| 7 to 9 | Incremental rebuild, freshness checks per clinic feed, a review queue for unmatched pets and broken invoices. | A stopped feed alerts within a day. |
| 10 to 13 | Hand the analyst a clean surface: documented marts, metric views, and the AI catalog for internal LLM tools. | The analyst ships answers without asking where data lives. |
