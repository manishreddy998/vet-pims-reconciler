-- Every patient record from every PIMS, with owner contact details and the clinic it belongs to.
with patients as (
    select 'cornerstone' as pims, p.*, c.first_name_norm as owner_first_name_norm, c.last_name_norm as owner_last_name_norm,
           c.email_norm as owner_email_norm, c.phone_digits as owner_phone_digits
    from {{ ref('stg_cornerstone__patients') }} p
    left join {{ ref('stg_cornerstone__clients') }} c using (client_source_key)
    union all
    select 'allydvm' as pims, p.*, c.first_name_norm, c.last_name_norm, c.email_norm, c.phone_digits
    from {{ ref('stg_allydvm__patients') }} p
    left join {{ ref('stg_allydvm__clients') }} c using (client_source_key)
)
select
    p.patient_source_key, p.client_source_key, p.pims, p.practice_id, pr.clinic_id, pr.is_current_feed,
    p.pims_patient_id, p.pet_name_raw, p.pet_name_norm, p.species, p.breed, p.birth_date, p.is_deceased, p.deceased_on,
    p.owner_first_name_norm, p.owner_last_name_norm, p.owner_email_norm, p.owner_phone_digits
from patients p
join {{ ref('int_practices') }} pr using (practice_id)
