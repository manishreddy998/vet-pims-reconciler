select
    ms.membership_id, ms.pet_id as app_pet_id, d.golden_patient_id, p.member_id, d.clinic_id,
    ms.plan_code, pl.plan_name, ms.monthly_price_cents, ms.started_on, ms.cancelled_on,
    ms.cancelled_on is null                                                as is_active,
    d.is_deceased and ms.cancelled_on is null                              as is_active_for_deceased_pet
from {{ ref('stg_app__memberships') }} ms
join {{ ref('stg_app__pets') }} p on p.pet_id = ms.pet_id
left join {{ ref('dim_patient') }} d on d.app_pet_id = ms.pet_id
left join {{ ref('plans') }} pl on pl.plan_code = ms.plan_code
