# Data catalog for AI tools

Generated from the dbt manifest on every build. Paste into a system prompt or serve it from a tool.

## Rules

- Only query the tables listed here. Never query raw_* or staging schemas.
- Count animals with golden_patient_id, never with PIMS patient ids.
- Bucket dates with local_date / invoice_local_date (clinic clock), not UTC.
- Money columns ending in _cents are integers in cents. Divide by 100 for dollars.
- Read-only. Add a LIMIT to exploratory queries.

## Glossary

- **appointment**: A booking for a patient at a clinic, from the PIMS that was that clinic's system of record on that date. Table: fct_appointment.
- **visit**: An appointment that happened: fct_appointment.is_visit (status completed). Count visits by local_date, never by UTC date.
- **patient**: A real animal: dim_patient.golden_patient_id. One animal can have several PIMS records; never count PIMS patient ids.
- **plan pet**: A patient enrolled in a wellness plan: dim_patient.is_plan_pet.
- **covered care**: Invoice lines the pet's plan paid for, within yearly limits: fct_invoice_line.is_plan_covered.
- **care to dues ratio**: Covered care value divided by dues collected. Above 1.0 means the plan paid out more than it collected.
- **net / gross**: net_cents is before tax, gross_cents includes tax. Revenue questions use net unless asked otherwise.

## Tables

### `marts.dim_clinic`

Grain: one row per clinic. Rows: 6.

One row per clinic, with the PIMS it runs today and whether it ever switched PIMS.

| column | type | meaning |
|---|---|---|
| clinic_id | VARCHAR | Clinic id (join to marts.dim_clinic). |
| clinic_name | VARCHAR | Clinic name. |
| clinic_timezone | VARCHAR | IANA time zone of the clinic. |
| sales_tax_rate | DECIMAL(6,4) | Sales tax rate applied at the clinic. |
| onboarded_on | DATE |  |
| current_pims | VARCHAR | PIMS the clinic runs today. |
| current_practice_id | VARCHAR |  |
| switched_pims | BOOLEAN | True if the clinic changed PIMS during the data window. |
| current_pims_since | DATE |  |

### `marts.dim_member`

Grain: one row per plan member. Rows: 1,414.

One row per plan member (pet owner) from the app.

| column | type | meaning |
|---|---|---|
| member_id | VARCHAR | Plan member (join to marts.dim_member). |
| first_name | VARCHAR |  |
| last_name | VARCHAR |  |
| email | VARCHAR |  |
| phone | VARCHAR |  |
| created_at_utc | TIMESTAMP |  |

### `marts.dim_patient`

Grain: one row per real animal (golden patient). Rows: 3,473.

The golden patient. One row per real animal, however many PIMS records and app rows describe it. Built by explicit, ranked matching rules (see int_patient_matches) so every link can be explained.

| column | type | meaning |
|---|---|---|
| golden_patient_id | VARCHAR | Stable id for the animal. Plan pets are keyed on their app pet id, so the id survives a clinic changing PIMS. |
| app_pet_id | VARCHAR | App pet id when the animal is on a wellness plan. |
| member_id | VARCHAR | Plan member (join to marts.dim_member). |
| clinic_id | VARCHAR | Clinic id (join to marts.dim_clinic). |
| pims_clinic_id | VARCHAR |  |
| pet_name | VARCHAR | Pet name (PIMS spelling when available). |
| species | VARCHAR | dog or cat. |
| breed | VARCHAR |  |
| birth_date | DATE |  |
| is_deceased | BOOLEAN | PIMS marks the animal deceased. |
| deceased_on | DATE |  |
| is_plan_pet | BOOLEAN |  |
| match_rule | VARCHAR | Which rule linked the app pet to the PIMS record, or not_found_in_pims. |
| match_confidence | DECIMAL(3,2) | 0.75 to 0.99. Anything under 0.95 goes to the review queue. |
| clinic_mismatch | BOOLEAN |  |
| n_pims_records | BIGINT | How many PIMS patient records describe this animal (2 for clinics that switched PIMS). |
| pims_record_keys | VARCHAR |  |

### `marts.fct_membership`

Grain: one row per plan membership. Rows: 1,596.

One row per wellness plan membership.

| column | type | meaning |
|---|---|---|
| membership_id | VARCHAR | Plan membership (join to marts.fct_membership). |
| app_pet_id | VARCHAR | Pet id in the plan app. |
| golden_patient_id | VARCHAR | The real animal (join to marts.dim_patient). |
| member_id | VARCHAR | Plan member (join to marts.dim_member). |
| clinic_id | VARCHAR | Clinic id (join to marts.dim_clinic). |
| plan_code | VARCHAR | Plan tier: ESSENTIAL, PLUS or COMPLETE. |
| plan_name | VARCHAR | Plan tier name. |
| monthly_price_cents | BIGINT | Monthly plan price in cents. |
| started_on | DATE | Membership start date. |
| cancelled_on | DATE | Membership cancellation date. |
| is_active | BOOLEAN | Membership not cancelled. |
| is_active_for_deceased_pet | BOOLEAN |  |

### `marts.fct_appointment`

Grain: one row per appointment in the clinic's system of record. Rows: 10,797.

THE definition of an appointment: a booking for a patient at a clinic, taken from the PIMS that was the clinic's system of record on that date, latest version only, on the clinic's local clock. A visit is an appointment with status completed.

| column | type | meaning |
|---|---|---|
| appointment_id | VARCHAR |  |
| golden_patient_id | VARCHAR | The real animal (join to marts.dim_patient). |
| clinic_id | VARCHAR | Clinic id (join to marts.dim_clinic). |
| source_pims | VARCHAR | PIMS the record came from: cornerstone or allydvm. |
| appointment_source_key | VARCHAR |  |
| start_utc | TIMESTAMP | Appointment start in UTC. |
| start_local | TIMESTAMP | Appointment start on the clinic's local clock. |
| local_date | DATE | Date on the clinic's own clock. Use this, not the UTC date, for any daily or monthly count. |
| appointment_type | VARCHAR | wellness, sick, dental or surgery. |
| duration_minutes | INTEGER |  |
| raw_status | VARCHAR |  |
| status | VARCHAR | scheduled, checked_in, completed, no_show, cancelled, or unresolved (still booked well after its start time). |
| is_visit | BOOLEAN | True when the appointment happened (status completed). |
| is_plan_pet | BOOLEAN |  |
| invoice_id | VARCHAR | Invoice (join to marts.fct_invoice). |
| n_source_versions | BIGINT |  |
| source_updated_at_utc | TIMESTAMP |  |

### `marts.fct_invoice`

Grain: one row per invoice. Rows: 8,561.

One row per invoice, on one money definition: net before tax, tax, gross.

| column | type | meaning |
|---|---|---|
| invoice_id | VARCHAR | Invoice (join to marts.fct_invoice). |
| invoice_source_key | VARCHAR |  |
| source_pims | VARCHAR | PIMS the record came from: cornerstone or allydvm. |
| clinic_id | VARCHAR | Clinic id (join to marts.dim_clinic). |
| golden_patient_id | VARCHAR | The real animal (join to marts.dim_patient). |
| invoice_local_date | DATE | Invoice date on the clinic's clock. |
| n_lines | BIGINT |  |
| net_cents | HUGEINT | Amount before tax, in cents. |
| tax_cents | HUGEINT | Tax in cents. |
| gross_cents | HUGEINT | Amount including tax, in cents. |
| math_gap_cents | HUGEINT |  |
| has_math_mismatch | BOOLEAN | Reported total does not equal lines plus tax. |
| is_voided | BOOLEAN | Voided in the PIMS. Exclude from revenue. |

### `marts.fct_invoice_line`

Grain: one row per invoice line. Rows: 28,388.

One row per invoice line with a canonical service and whether the pet's plan covered it (respecting yearly limits).

| column | type | meaning |
|---|---|---|
| invoice_line_id | VARCHAR |  |
| invoice_id | VARCHAR | Invoice (join to marts.fct_invoice). |
| invoice_line_source_key | VARCHAR |  |
| source_pims | VARCHAR | PIMS the record came from: cornerstone or allydvm. |
| clinic_id | VARCHAR | Clinic id (join to marts.dim_clinic). |
| golden_patient_id | VARCHAR | The real animal (join to marts.dim_patient). |
| invoice_local_date | DATE | Invoice date on the clinic's clock. |
| item_code | VARCHAR |  |
| item_description | VARCHAR |  |
| quantity | INTEGER |  |
| unit_price_cents | BIGINT |  |
| discount_cents | BIGINT |  |
| line_net_cents | BIGINT | Line amount after discount, before tax, in cents. |
| canonical_service | VARCHAR | Service in one vocabulary across PIMS. |
| service_category | VARCHAR | Group of the canonical service. |
| is_unmapped_item | BOOLEAN |  |
| membership_id | VARCHAR | Plan membership (join to marts.fct_membership). |
| plan_code | VARCHAR | Plan tier: ESSENTIAL, PLUS or COMPLETE. |
| membership_year | INTEGER |  |
| is_plan_covered | BOOLEAN | True when the service is in the member's plan and within its yearly limit, on the invoice date. |
| is_over_plan_limit | BOOLEAN |  |
| is_voided | BOOLEAN | Voided in the PIMS. Exclude from revenue. |

### `marts.fct_membership_month`

Grain: one row per membership per active month. Rows: 16,302.

One row per membership per active month: dues collected, covered care value, uncovered care, visits.

| column | type | meaning |
|---|---|---|
| membership_id | VARCHAR | Plan membership (join to marts.fct_membership). |
| month_start | DATE | First day of the month. |
| golden_patient_id | VARCHAR | The real animal (join to marts.dim_patient). |
| clinic_id | VARCHAR | Clinic id (join to marts.dim_clinic). |
| plan_code | VARCHAR | Plan tier: ESSENTIAL, PLUS or COMPLETE. |
| monthly_price_cents | BIGINT | Monthly plan price in cents. |
| dues_collected_cents | HUGEINT | Plan dues collected in the month (refunds negative), in cents. |
| failed_charges | HUGEINT |  |
| covered_care_cents | HUGEINT | Value of care the plan covered in the month, in cents. |
| uncovered_care_cents | HUGEINT |  |
| visits | BIGINT | Completed visits. |

### `metrics.metric_plan_economics_monthly`

Grain: one row per month per plan. Rows: 60.

Approved metric. Plan economics by month and tier. care_to_dues_ratio = covered care value / dues collected.

| column | type | meaning |
|---|---|---|
| month_start | DATE | First day of the month. |
| plan_code | VARCHAR | Plan tier: ESSENTIAL, PLUS or COMPLETE. |
| active_memberships | BIGINT |  |
| dues_collected | DOUBLE |  |
| covered_care_value | DOUBLE |  |
| care_to_dues_ratio | DOUBLE |  |
| visits_per_100_memberships | DOUBLE |  |
| failed_charges | HUGEINT |  |

### `metrics.metric_clinic_monthly`

Grain: one row per clinic per month. Rows: 78.

Approved metric. Clinic scorecard by month on the canonical appointment definition.

| column | type | meaning |
|---|---|---|
| clinic_id | VARCHAR | Clinic id (join to marts.dim_clinic). |
| clinic_name | VARCHAR | Clinic name. |
| month_start | DATE | First day of the month. |
| appointments | BIGINT |  |
| visits | HUGEINT | Completed visits. |
| no_show_rate | DOUBLE |  |
| cancel_rate | DOUBLE |  |
| plan_pet_visit_share | DOUBLE |  |

### `reports.rpt_reconciliation_issues`

Grain: one row per data issue. Rows: 765.

Every decision the pipeline made or could not make, one row per issue, with severity. This is the ops review queue.

| column | type | meaning |
|---|---|---|
| issue_id | VARCHAR |  |
| issue_type | VARCHAR | Kind of data issue. |
| severity | VARCHAR | high, medium, low or info. |
| clinic_id | VARCHAR | Clinic id (join to marts.dim_clinic). |
| entity_type | VARCHAR |  |
| entity_key | VARCHAR | Source key of the record the issue is about. |
| detail | VARCHAR | Human-readable explanation of the issue. |
| clinic_name | VARCHAR | Clinic name. |

## Vetted SQL

**How many visits did each clinic have last month?**

```sql
select c.clinic_name, count(*) as visits from marts.fct_appointment a join marts.dim_clinic c using (clinic_id) where a.is_visit and a.local_date >= date_trunc('month', current_date) - interval '1 month' and a.local_date < date_trunc('month', current_date) group by 1 order by 2 desc
```

**Which plan tier pays out the most care relative to dues?**

```sql
select plan_code, sum(covered_care_value) / nullif(sum(dues_collected), 0) as care_to_dues_ratio from metrics.metric_plan_economics_monthly group by 1 order by 2 desc
```

**What is the no-show rate by clinic over the last 3 months?**

```sql
select clinic_name, sum(appointments * no_show_rate) / sum(appointments) as no_show_rate from metrics.metric_clinic_monthly where month_start >= date_trunc('month', current_date) - interval '3 month' group by 1 order by 2 desc
```

**Which high-severity data issues need attention?**

```sql
select issue_type, clinic_name, count(*) from reports.rpt_reconciliation_issues where severity = 'high' group by 1, 2 order by 3 desc
```
