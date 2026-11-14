"""Export an LLM-ready catalog of the approved tables, built from dbt's own manifest and catalog.

Internal AI tools should not guess at raw PIMS tables. This gives them a small, curated surface:
which tables to use, what one row means, what each column means, the business glossary, and vetted SQL
for common questions. It is regenerated on every build, so it never drifts from the warehouse.

Usage: dbt docs generate && python scripts/export_llm_catalog.py
Writes llm_context/catalog.json (for tools) and llm_context/catalog.md (for prompts and people).
"""
import json, os
import duckdb

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
manifest = json.load(open(os.path.join(ROOT, "target", "manifest.json")))
catalog = json.load(open(os.path.join(ROOT, "target", "catalog.json")))

APPROVED = ["dim_clinic", "dim_member", "dim_patient", "fct_membership", "fct_appointment", "fct_invoice",
            "fct_invoice_line", "fct_membership_month", "metric_plan_economics_monthly", "metric_clinic_monthly",
            "rpt_reconciliation_issues"]
GRAIN = {
    "dim_clinic": "one row per clinic", "dim_member": "one row per plan member", "dim_patient": "one row per real animal (golden patient)",
    "fct_membership": "one row per plan membership", "fct_appointment": "one row per appointment in the clinic's system of record",
    "fct_invoice": "one row per invoice", "fct_invoice_line": "one row per invoice line",
    "fct_membership_month": "one row per membership per active month", "metric_plan_economics_monthly": "one row per month per plan",
    "metric_clinic_monthly": "one row per clinic per month", "rpt_reconciliation_issues": "one row per data issue",
}
GLOSSARY = {
    "appointment": "A booking for a patient at a clinic, from the PIMS that was that clinic's system of record on that date. Table: fct_appointment.",
    "visit": "An appointment that happened: fct_appointment.is_visit (status completed). Count visits by local_date, never by UTC date.",
    "patient": "A real animal: dim_patient.golden_patient_id. One animal can have several PIMS records; never count PIMS patient ids.",
    "plan pet": "A patient enrolled in a wellness plan: dim_patient.is_plan_pet.",
    "covered care": "Invoice lines the pet's plan paid for, within yearly limits: fct_invoice_line.is_plan_covered.",
    "care to dues ratio": "Covered care value divided by dues collected. Above 1.0 means the plan paid out more than it collected.",
    "net / gross": "net_cents is before tax, gross_cents includes tax. Revenue questions use net unless asked otherwise.",
}
VETTED_SQL = [
    ("How many visits did each clinic have last month?",
     "select c.clinic_name, count(*) as visits from marts.fct_appointment a join marts.dim_clinic c using (clinic_id) "
     "where a.is_visit and a.local_date >= date_trunc('month', current_date) - interval '1 month' "
     "and a.local_date < date_trunc('month', current_date) group by 1 order by 2 desc"),
    ("Which plan tier pays out the most care relative to dues?",
     "select plan_code, sum(covered_care_value) / nullif(sum(dues_collected), 0) as care_to_dues_ratio "
     "from metrics.metric_plan_economics_monthly group by 1 order by 2 desc"),
    ("What is the no-show rate by clinic over the last 3 months?",
     "select clinic_name, sum(appointments * no_show_rate) / sum(appointments) as no_show_rate from metrics.metric_clinic_monthly "
     "where month_start >= date_trunc('month', current_date) - interval '3 month' group by 1 order by 2 desc"),
    ("Which high-severity data issues need attention?",
     "select issue_type, clinic_name, count(*) from reports.rpt_reconciliation_issues where severity = 'high' group by 1, 2 order by 3 desc"),
]
# fallback meanings for columns that are not documented in a model's yml
COMMON = {
    "clinic_id": "Clinic id (join to marts.dim_clinic).", "clinic_name": "Clinic name.", "clinic_timezone": "IANA time zone of the clinic.",
    "golden_patient_id": "The real animal (join to marts.dim_patient).", "member_id": "Plan member (join to marts.dim_member).",
    "membership_id": "Plan membership (join to marts.fct_membership).", "invoice_id": "Invoice (join to marts.fct_invoice).",
    "app_pet_id": "Pet id in the plan app.", "plan_code": "Plan tier: ESSENTIAL, PLUS or COMPLETE.", "plan_name": "Plan tier name.",
    "source_pims": "PIMS the record came from: cornerstone or allydvm.", "current_pims": "PIMS the clinic runs today.",
    "switched_pims": "True if the clinic changed PIMS during the data window.", "sales_tax_rate": "Sales tax rate applied at the clinic.",
    "start_utc": "Appointment start in UTC.", "start_local": "Appointment start on the clinic's local clock.",
    "appointment_type": "wellness, sick, dental or surgery.", "invoice_local_date": "Invoice date on the clinic's clock.",
    "net_cents": "Amount before tax, in cents.", "tax_cents": "Tax in cents.", "gross_cents": "Amount including tax, in cents.",
    "line_net_cents": "Line amount after discount, before tax, in cents.", "canonical_service": "Service in one vocabulary across PIMS.",
    "service_category": "Group of the canonical service.", "is_voided": "Voided in the PIMS. Exclude from revenue.",
    "has_math_mismatch": "Reported total does not equal lines plus tax.", "month_start": "First day of the month.",
    "dues_collected_cents": "Plan dues collected in the month (refunds negative), in cents.",
    "covered_care_cents": "Value of care the plan covered in the month, in cents.", "visits": "Completed visits.",
    "is_active": "Membership not cancelled.", "started_on": "Membership start date.", "cancelled_on": "Membership cancellation date.",
    "monthly_price_cents": "Monthly plan price in cents.", "severity": "high, medium, low or info.", "issue_type": "Kind of data issue.",
    "detail": "Human-readable explanation of the issue.", "entity_key": "Source key of the record the issue is about.",
    "pet_name": "Pet name (PIMS spelling when available).", "species": "dog or cat.", "is_deceased": "PIMS marks the animal deceased.",
}

RULES = [
    "Only query the tables listed here. Never query raw_* or staging schemas.",
    "Count animals with golden_patient_id, never with PIMS patient ids.",
    "Bucket dates with local_date / invoice_local_date (clinic clock), not UTC.",
    "Money columns ending in _cents are integers in cents. Divide by 100 for dollars.",
    "Read-only. Add a LIMIT to exploratory queries.",
]

con = duckdb.connect(os.path.join(ROOT, "warehouse.duckdb"), read_only=True)
tables = []
for node in manifest["nodes"].values():
    if node["resource_type"] != "model" or node["name"] not in APPROVED:
        continue
    cat = catalog["nodes"].get(node["unique_id"], {})
    cols = []
    for cname, c in (cat.get("columns") or {}).items():
        doc = (node["columns"].get(cname.lower()) or {}).get("description", "") or COMMON.get(cname.lower(), "")
        cols.append({"name": cname.lower(), "type": c["type"], "description": doc})
    rel = f'{node["schema"]}.{node["name"]}'
    n = con.sql(f"select count(*) from {rel}").fetchall()[0][0]
    tables.append({"table": rel, "grain": GRAIN.get(node["name"], ""), "description": " ".join(node["description"].split()),
                   "row_count": n, "upstream": [d.split(".")[-1] for d in node["depends_on"]["nodes"]], "columns": cols})
tables.sort(key=lambda t: APPROVED.index(t["table"].split(".")[1]))

out = {"rules": RULES, "glossary": GLOSSARY, "tables": tables, "vetted_sql": [{"question": q, "sql": s} for q, s in VETTED_SQL]}
os.makedirs(os.path.join(ROOT, "llm_context"), exist_ok=True)
json.dump(out, open(os.path.join(ROOT, "llm_context", "catalog.json"), "w"), indent=2, default=str)

md = ["# Data catalog for AI tools", "", "Generated from the dbt manifest on every build. Paste into a system prompt or serve it from a tool.", "",
      "## Rules", ""] + [f"- {r}" for r in RULES] + ["", "## Glossary", ""] + [f"- **{k}**: {v}" for k, v in GLOSSARY.items()] + ["", "## Tables", ""]
for t in tables:
    md += [f"### `{t['table']}`", "", f"Grain: {t['grain']}. Rows: {t['row_count']:,}.", "", t["description"], "",
           "| column | type | meaning |", "|---|---|---|"]
    md += [f"| {c['name']} | {c['type']} | {c['description']} |" for c in t["columns"]]
    md.append("")
md += ["## Vetted SQL", ""]
for q, s in VETTED_SQL:
    md += [f"**{q}**", "", "```sql", s, "```", ""]
open(os.path.join(ROOT, "llm_context", "catalog.md"), "w").write("\n".join(md))
# sanity: every vetted query must run
for q, s in VETTED_SQL:
    con.sql(s).fetchall()
print(f"catalog: {len(tables)} approved tables, {sum(len(t['columns']) for t in tables)} columns, {len(VETTED_SQL)} vetted queries (all run)")
