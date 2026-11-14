-- Fail if more than 5% of plan pets cannot be found in any PIMS. A jump here means a matching rule broke
-- or a clinic feed changed shape. Individual misses are listed in rpt_reconciliation_issues.
select count(*) filter (where n_pims_records = 0) * 1.0 / count(*) as unmatched_share
from {{ ref('dim_patient') }}
where is_plan_pet
having count(*) filter (where n_pims_records = 0) * 1.0 / count(*) > 0.05
