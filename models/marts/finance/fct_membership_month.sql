-- One row per membership per month it was active: what the member paid and what care the plan covered.
with months as (
    select cast(generate_series as date) as month_start
    from generate_series(cast(date_trunc('month', (select min(started_on) from {{ ref('fct_membership') }})) as timestamp),
                         cast(date_trunc('month', current_date) as timestamp), interval '1 month')
),
mm as (
    select m.membership_id, m.golden_patient_id, m.clinic_id, m.plan_code, m.monthly_price_cents, mo.month_start
    from {{ ref('fct_membership') }} m
    join months mo
      on mo.month_start >= cast(date_trunc('month', m.started_on) as date)
     and mo.month_start <= cast(date_trunc('month', coalesce(m.cancelled_on, current_date)) as date)
),
pay as (
    select membership_id, cast(date_trunc('month', charged_at_utc) as date) as month_start,
           sum(case when status in ('succeeded', 'refunded') then amount_cents else 0 end) as dues_collected_cents,
           sum(case when status = 'failed' then 1 else 0 end)                           as failed_charges
    from {{ ref('stg_app__payments') }} group by 1, 2
),
care as (
    select membership_id, cast(date_trunc('month', invoice_local_date) as date) as month_start,
           sum(case when is_plan_covered then line_net_cents else 0 end) as covered_care_cents,
           sum(case when not is_voided and not coalesce(is_plan_covered, false) then line_net_cents else 0 end) as uncovered_care_cents
    from {{ ref('fct_invoice_line') }} where membership_id is not null group by 1, 2
),
visits as (
    select golden_patient_id, cast(date_trunc('month', local_date) as date) as month_start, count(*) as visits
    from {{ ref('fct_appointment') }} where is_visit group by 1, 2
)
select
    mm.membership_id, mm.month_start, mm.golden_patient_id, mm.clinic_id, mm.plan_code, mm.monthly_price_cents,
    coalesce(p.dues_collected_cents, 0)   as dues_collected_cents,
    coalesce(p.failed_charges, 0)         as failed_charges,
    coalesce(c.covered_care_cents, 0)     as covered_care_cents,
    coalesce(c.uncovered_care_cents, 0)   as uncovered_care_cents,
    coalesce(v.visits, 0)                 as visits
from mm
left join pay p on p.membership_id = mm.membership_id and p.month_start = mm.month_start
left join care c on c.membership_id = mm.membership_id and c.month_start = mm.month_start
left join visits v on v.golden_patient_id = mm.golden_patient_id and v.month_start = mm.month_start
