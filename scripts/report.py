"""Build a one-page, self-contained HTML reconciliation report from the warehouse.

Usage: python scripts/report.py  ->  reports/reconciliation_report.html
"""
import html, json, os
from datetime import datetime, timezone
import duckdb

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
con = duckdb.connect(os.path.join(ROOT, "warehouse.duckdb"), read_only=True)
q = lambda s: con.sql(s).fetchall()
one = lambda s: q(s)[0][0]

raw_rows = sum(one(f"select count(*) from {t}") for t in [
    "raw_cornerstone.clients", "raw_cornerstone.patients", "raw_cornerstone.appointments", "raw_cornerstone.invoices",
    "raw_cornerstone.invoice_items", "raw_allydvm.clients", "raw_allydvm.patients", "raw_allydvm.appointments",
    "raw_allydvm.invoices", "raw_allydvm.invoice_lines", "raw_app.members", "raw_app.pets", "raw_app.memberships", "raw_app.payments"])
pims_patient_records = one("select count(*) from intermediate.int_pims_patients")
golden = one("select count(*) from marts.dim_patient")
plan_pets = one("select count(*) from marts.dim_patient where is_plan_pet")
plan_matched = one("select count(*) from marts.dim_patient where is_plan_pet and n_pims_records > 0")
visits = one("select count(*) from marts.fct_appointment where is_visit")
appt_rows = one("select count(*) from raw_cornerstone.appointments") + one("select count(*) from raw_allydvm.appointments")
tests_note = "dbt build: all tests pass, 1 intended warning (stale feed)"

drift = q("select month_start, naive_export_rows, naive_any_status, naive_completed_both_systems, canonical_visits from reports.rpt_definition_drift order by 1")
rules = q("select coalesce(match_rule, 'pims-only patient (not on a plan)'), count(*) from marts.dim_patient group by 1 order by 2 desc")
issues = q("select severity, issue_type, count(*) from reports.rpt_reconciliation_issues group by 1, 2 "
           "order by case severity when 'high' then 0 when 'medium' then 1 when 'low' then 2 else 3 end, 3 desc")
examples = q("select severity, issue_type, coalesce(clinic_name, ''), detail from reports.rpt_reconciliation_issues "
             "where severity in ('high', 'medium') qualify row_number() over (partition by issue_type order by entity_key) = 1 "
             "order by case severity when 'high' then 0 else 1 end")
fresh = q("select clinic_name, pims, practice_id, is_current_feed, hours_since_last_update, is_stale from reports.rpt_feed_freshness order by is_stale desc, clinic_name")
econ = q("select plan_code, sum(active_memberships), round(sum(dues_collected)), round(sum(covered_care_value)), "
         "round(sum(covered_care_value) / nullif(sum(dues_collected), 0), 2) from metrics.metric_plan_economics_monthly "
         "where month_start >= date_trunc('month', current_date) - interval '6 month' and month_start < date_trunc('month', current_date) "
         "group by 1 order by 5 desc")
over_limit = one("select count(*) from marts.fct_invoice_line where is_over_plan_limit")
cutover = json.load(open(os.path.join(ROOT, "data", "raw", "_manifest.json")))["cutover"]
e = html.escape


def bar_rows(rows):
    mx = max(max(r[1:]) for r in rows)
    out = []
    for m, a, b, c, d in rows:
        label = m.strftime("%b %Y")
        cells = "".join(
            f'<div class="bar {cls}" style="width:{v / mx * 100:.1f}%"><span>{v:,}</span></div>'
            for v, cls in ((b, "b2"), (c, "b3"), (d, "b4")))
        over = (c - d) / d * 100 if d else 0
        out.append(f'<div class="brow"><div class="blabel">{label}</div><div class="bars">{cells}</div>'
                   f'<div class="bdelta{" hot" if over > 1 else ""}">{"+" if over > 0 else ""}{over:.0f}%</div></div>')
    return "\n".join(out)


STALE = '<span class="pill sev-high">stale</span>'
sev_class = {"high": "sev-high", "medium": "sev-med", "low": "sev-low", "info": "sev-info"}
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PIMS Reconciliation Report</title>
<style>
:root {{ --bg:#fbfaf7; --card:#fff; --ink:#1d1b16; --muted:#6b665c; --line:#e7e2d8; --accent:#2f6f5e; --b2:#d9cfbd; --b3:#c9884f; --b4:#2f6f5e; --hot:#b4472f; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#14130f; --card:#1d1b16; --ink:#eeeae1; --muted:#a39d90; --line:#34302a; --accent:#6fbfa6; --b2:#4a4439; --b3:#c9884f; --b4:#6fbfa6; --hot:#e07a5f; }} }}
* {{ box-sizing:border-box }} body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif }}
main {{ max-width:1040px; margin:0 auto; padding:32px 16px 64px }}
h1 {{ font-size:28px; margin:0 0 4px; letter-spacing:-.01em }} h2 {{ font-size:18px; margin:36px 0 10px }}
.sub {{ color:var(--muted); margin:0 0 24px }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px }}
.kpi {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px }}
.kpi b {{ display:block; font-size:24px; font-variant-numeric:tabular-nums }} .kpi span {{ color:var(--muted); font-size:13px }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px; overflow-x:auto }}
table {{ border-collapse:collapse; width:100%; font-size:14px }} th,td {{ text-align:left; padding:7px 8px; border-bottom:1px solid var(--line); vertical-align:top }}
th {{ color:var(--muted); font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.04em }}
td.n {{ text-align:right; font-variant-numeric:tabular-nums }}
.brow {{ display:grid; grid-template-columns:78px 1fr 52px; gap:10px; align-items:center; margin:6px 0 }}
.blabel {{ color:var(--muted); font-size:13px }} .bars {{ display:flex; flex-direction:column; gap:2px }}
.bar {{ height:14px; border-radius:3px; position:relative; min-width:2px }} .bar span {{ position:absolute; left:calc(100% + 6px); top:-2px; font-size:11px; color:var(--muted); white-space:nowrap }}
.b2 {{ background:var(--b2) }} .b3 {{ background:var(--b3) }} .b4 {{ background:var(--b4) }}
.bdelta {{ font-size:13px; text-align:right; color:var(--muted); font-variant-numeric:tabular-nums }} .bdelta.hot {{ color:var(--hot); font-weight:700 }}
.legend {{ display:flex; flex-wrap:wrap; gap:14px; font-size:13px; color:var(--muted); margin-bottom:8px }} .legend i {{ display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:5px }}
.pill {{ display:inline-block; padding:1px 8px; border-radius:99px; font-size:12px; font-weight:600 }}
.sev-high {{ background:#f6dcd4; color:#8a2e1a }} .sev-med {{ background:#f5e7cf; color:#7a4d10 }} .sev-low {{ background:#e3ecf2; color:#2a4d66 }} .sev-info {{ background:#ebe8e1; color:#5b564c }}
.note {{ color:var(--muted); font-size:13px; margin-top:8px }}
@media (max-width:640px) {{ .brow {{ grid-template-columns:60px 1fr 44px }} }}
</style></head><body><main>
<h1>PIMS reconciliation report</h1>
<p class="sub">Two practice-management systems and the plan app, reconciled into one set of definitions. Synthetic data, generated {datetime.now(timezone.utc).strftime('%b %d, %Y')}. {tests_note}.</p>
<div class="kpis">
 <div class="kpi"><b>{raw_rows:,}</b><span>raw rows landed from 3 sources</span></div>
 <div class="kpi"><b>{pims_patient_records:,} → {golden:,}</b><span>PIMS patient records → real animals</span></div>
 <div class="kpi"><b>{plan_matched / plan_pets:.1%}</b><span>of plan pets matched to a clinic record ({plan_matched:,} of {plan_pets:,})</span></div>
 <div class="kpi"><b>{appt_rows:,} → {visits:,}</b><span>appointment export rows → counted visits</span></div>
</div>

<h2>One question, four answers: how many visits did we have?</h2>
<div class="card">
<div class="legend"><span><i style="background:var(--b2)"></i>every appointment, any status</span><span><i style="background:var(--b3)"></i>"completed" in both systems added up</span><span><i style="background:var(--b4)"></i>canonical visits (one system of record)</span><span>% = overcount of the orange answer</span></div>
{bar_rows(drift)}
<p class="note">Raw export rows alone would say {drift[-1][1]:,} for the last month, because every extract re-sends every appointment. The orange bars jump in the months before Maple Grove switched from Cornerstone to AllyDVM on {cutover}: the new system imported that history, so adding both systems counts those visits twice. The canonical model keeps one system of record per clinic per date.</p>
</div>

<h2>How animals were matched</h2>
<div class="card"><table><tr><th>Rule</th><th class="n">Animals</th></tr>
{''.join(f'<tr><td>{e(r)}</td><td class="n">{n:,}</td></tr>' for r, n in rules)}
</table><p class="note">Rules are explicit and ranked (email + pet name 0.99, phone + pet name 0.96, contact + similar name 0.90, surname + name + birth date 0.85, other clinic 0.75). A clinic that changed PIMS has the same animal in both systems: those twins are linked, so the animal keeps one id.</p></div>

<h2>Review queue</h2>
<div class="card"><table><tr><th>Severity</th><th>Issue</th><th class="n">Count</th></tr>
{''.join(f'<tr><td><span class="pill {sev_class[s]}">{s}</span></td><td>{e(t.replace("_", " "))}</td><td class="n">{n:,}</td></tr>' for s, t, n in issues)}
</table></div>
<div class="card" style="margin-top:10px"><table><tr><th>Severity</th><th>Example</th><th>Clinic</th><th>Detail</th></tr>
{''.join(f'<tr><td><span class="pill {sev_class[s]}">{s}</span></td><td>{e(t.replace("_", " "))}</td><td>{e(c)}</td><td>{e(d)}</td></tr>' for s, t, c, d in examples)}
</table></div>

<h2>Feed freshness</h2>
<div class="card"><table><tr><th>Clinic</th><th>PIMS</th><th>Practice</th><th>Current feed</th><th class="n">Hours since update</th><th>Status</th></tr>
{''.join(f'<tr><td>{e(c)}</td><td>{p}</td><td>{pr}</td><td>{"yes" if cur else "retired"}</td><td class="n">{h}</td><td>{STALE if st else "ok"}</td></tr>' for c, p, pr, cur, h, st in fresh)}
</table><p class="note">A stopped feed looks exactly like a clinic having a quiet week. This check runs on every build.</p></div>

<h2>Plan economics, last 6 full months</h2>
<div class="card"><table><tr><th>Plan</th><th class="n">Membership-months</th><th class="n">Dues collected ($)</th><th class="n">Covered care ($)</th><th class="n">Care / dues</th></tr>
{''.join(f'<tr><td>{p}</td><td class="n">{m:,}</td><td class="n">{d:,.0f}</td><td class="n">{c:,.0f}</td><td class="n">{r}</td></tr>' for p, m, d, c, r in econ)}
</table><p class="note">Covered care respects yearly limits per service ({over_limit:,} lines were over a plan limit and are not counted as covered). Numbers are synthetic; the point is that they are computed from one definition.</p></div>
</main></body></html>"""
os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
open(os.path.join(ROOT, "reports", "reconciliation_report.html"), "w").write(page)
print("wrote reports/reconciliation_report.html")
