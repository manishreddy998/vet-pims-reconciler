select
    c.clinic_id, c.clinic_name, c.clinic_timezone, c.sales_tax_rate, c.onboarded_on,
    max(case when p.is_current_feed then p.pims end)                      as current_pims,
    max(case when p.is_current_feed then p.practice_id end)               as current_practice_id,
    count(*) > 1                                                          as switched_pims,
    min(case when p.is_current_feed then p.active_from end)               as current_pims_since
from {{ ref('stg_app__clinics') }} c
join {{ ref('int_practices') }} p using (clinic_id)
group by 1, 2, 3, 4, 5
