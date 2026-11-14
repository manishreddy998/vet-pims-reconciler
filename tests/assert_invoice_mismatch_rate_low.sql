{{ config(severity='warn') }}
-- Warn when more than 5% of posted invoices do not add up. Individual mismatches go to the issues report.
select pims, avg(case when has_math_mismatch then 1.0 else 0 end) as mismatch_rate
from {{ ref('int_invoices') }}
where not is_voided
group by pims
having avg(case when has_math_mismatch then 1.0 else 0 end) > 0.05
