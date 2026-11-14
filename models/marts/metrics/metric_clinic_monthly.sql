-- Clinic scorecard by month, on the canonical appointment definition.
select
    a.clinic_id, c.clinic_name, cast(date_trunc('month', a.local_date) as date)            as month_start,
    count(*)                                                                               as appointments,
    sum(case when a.is_visit then 1 else 0 end)                                            as visits,
    round(avg(case when a.status = 'no_show' then 1.0 else 0 end), 3)                      as no_show_rate,
    round(avg(case when a.status = 'cancelled' then 1.0 else 0 end), 3)                    as cancel_rate,
    round(sum(case when a.is_visit and a.is_plan_pet then 1.0 else 0 end)
          / nullif(sum(case when a.is_visit then 1 else 0 end), 0), 3)                     as plan_pet_visit_share
from {{ ref('fct_appointment') }} a
join {{ ref('dim_clinic') }} c using (clinic_id)
where a.local_date <= current_date
group by 1, 2, 3
