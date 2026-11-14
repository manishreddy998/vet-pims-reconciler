-- Plan economics by month and tier: dues in vs covered care out. care_to_dues_ratio above 1 means the plan pays out more than it collects.
select
    month_start, plan_code,
    count(*)                                                                  as active_memberships,
    sum(dues_collected_cents) / 100.0                                         as dues_collected,
    sum(covered_care_cents) / 100.0                                           as covered_care_value,
    round(sum(covered_care_cents) * 1.0 / nullif(sum(dues_collected_cents), 0), 3) as care_to_dues_ratio,
    round(sum(visits) * 100.0 / count(*), 1)                                  as visits_per_100_memberships,
    sum(failed_charges)                                                       as failed_charges
from {{ ref('fct_membership_month') }}
group by 1, 2
