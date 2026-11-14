"""Land raw PIMS and app exports into the warehouse exactly as they arrive (all text), with load metadata.

Raw tables are never cleaned here. Every fix happens in dbt so it is versioned, tested and documented.
Default target is a local DuckDB file. The dbt models use portable SQL, so the same project runs on Postgres.

Usage: python scripts/load.py [--db warehouse.duckdb]
"""
import argparse, csv, json, os, tempfile
from datetime import datetime, timezone
import duckdb

p = argparse.ArgumentParser()
root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
p.add_argument("--db", default=os.path.join(root, "warehouse.duckdb"))
p.add_argument("--raw", default=os.path.join(root, "data", "raw"))
p.add_argument("--target", choices=["duckdb", "postgres"], default="duckdb",
               help="postgres: land into the database named by PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE")
a = p.parse_args()
con = duckdb.connect(a.db if a.target == "duckdb" else ":memory:")
loaded_at = datetime.now(timezone.utc).isoformat()


def land(schema, table, rows, source_file):
    con.execute(f"create schema if not exists {schema}")
    con.execute(f"drop table if exists {schema}.{table}")
    if not rows:
        return 0
    cols = list(rows[0].keys())
    # stage as newline-delimited JSON with every value as text, then bulk-load (fast, and nothing gets typed early)
    with tempfile.NamedTemporaryFile("w", suffix=".ndjson", delete=False) as f:
        for r in rows:
            f.write(json.dumps({c: (None if r.get(c) in (None, "") else str(r.get(c))) for c in cols}) + "\n")
        tmp = f.name
    colspec = "{" + ", ".join(f"'{c}': 'VARCHAR'" for c in cols) + "}"
    con.execute(f"create table {schema}.{table} as select *, ? as _source_file, ? as _loaded_at "
                f"from read_json(?, format='newline_delimited', columns={colspec})", [source_file, loaded_at, tmp])
    os.unlink(tmp)
    return len(rows)


def read_csv(name):
    with open(os.path.join(a.raw, name)) as f:
        return list(csv.DictReader(f))


def read_jsonl(name):
    with open(os.path.join(a.raw, name)) as f:
        return [json.loads(l) for l in f if l.strip()]


counts = {}
for t in ["clients", "patients", "appointments", "invoices", "invoice_items"]:
    counts[f"raw_cornerstone.{t}"] = land("raw_cornerstone", t, read_csv(f"cornerstone_{t}.csv"), f"cornerstone_{t}.csv")

clients = read_jsonl("allydvm_clients.jsonl")
for c in clients:  # arrays arrive as JSON; keep the full payload and expose the first value
    c["primaryEmail"] = (c.get("emails") or [None])[0]
    c["primaryPhone"] = (c.get("phones") or [None])[0]
    c["emails"] = json.dumps(c.get("emails")); c["phones"] = json.dumps(c.get("phones"))
counts["raw_allydvm.clients"] = land("raw_allydvm", "clients", clients, "allydvm_clients.jsonl")
counts["raw_allydvm.patients"] = land("raw_allydvm", "patients", read_jsonl("allydvm_patients.jsonl"), "allydvm_patients.jsonl")
counts["raw_allydvm.appointments"] = land("raw_allydvm", "appointments", read_jsonl("allydvm_appointments.jsonl"), "allydvm_appointments.jsonl")
invoices = read_jsonl("allydvm_invoices.jsonl")
lines = []
for inv in invoices:  # nested line items are flattened at landing, one row per line with its parent key
    for n, ln in enumerate(inv.pop("lines"), 1):
        lines.append(dict(invoiceGuid=inv["invoiceGuid"], practiceId=inv["practiceId"], lineNumber=n, **ln, updatedAt=inv["updatedAt"]))
counts["raw_allydvm.invoices"] = land("raw_allydvm", "invoices", invoices, "allydvm_invoices.jsonl")
counts["raw_allydvm.invoice_lines"] = land("raw_allydvm", "invoice_lines", lines, "allydvm_invoices.jsonl")

for t in ["members", "pets", "memberships", "payments", "clinics", "clinic_pims_links"]:
    counts[f"raw_app.{t}"] = land("raw_app", t, read_csv(f"app_{t}.csv"), f"app_{t}.csv")

if a.target == "postgres":
    # copy the landed tables into Postgres with lower-case column names (Postgres folds unquoted identifiers)
    dsn = " ".join(f"{k}={os.environ[e]}" for k, e in [("host", "PGHOST"), ("port", "PGPORT"), ("user", "PGUSER"),
                                                       ("password", "PGPASSWORD"), ("dbname", "PGDATABASE")] if os.environ.get(e))
    con.execute("install postgres; load postgres")
    con.execute(f"attach '{dsn}' as pg (type postgres)")
    for full in counts:
        schema, table = full.split(".")
        cols = [r[0] for r in con.execute(f"describe {schema}.{table}").fetchall()]
        con.execute(f"create schema if not exists pg.{schema}")
        con.execute(f"drop table if exists pg.{schema}.{table}")
        con.execute(f"create table pg.{schema}.{table} as select {', '.join(f'{c} as {c.lower()}' for c in cols)} from {schema}.{table}")

for k, v in counts.items():
    print(f"{k:34s} {v:>8,}")
con.close()
