-- The golden patient: one row per real animal, however many PIMS records and app rows describe it.
with records as (
    select x.golden_patient_id, x.app_pet_id, x.match_rule, x.match_confidence, x.clinic_mismatch, x.patient_source_key,
           p.pims, p.clinic_id, p.is_current_feed, p.pet_name_raw, p.species, p.breed, p.birth_date, p.is_deceased, p.deceased_on
    from {{ ref('int_patient_xref') }} x
    join {{ ref('int_pims_patients') }} p using (patient_source_key)
),
from_pims as (
    select
        golden_patient_id,
        max(app_pet_id)                                                    as app_pet_id,
        max(match_rule)                                                    as match_rule,
        max(match_confidence)                                              as match_confidence,
        bool_or(clinic_mismatch)                                           as clinic_mismatch,
        -- prefer the record from the clinic's current PIMS
        max(case when is_current_feed then clinic_id end)                  as pims_clinic_id,
        max(case when is_current_feed then pet_name_raw end)               as pims_pet_name,
        max(species)                                                       as species,
        max(breed)                                                         as breed,
        max(birth_date)                                                    as pims_birth_date,
        bool_or(is_deceased)                                               as is_deceased,
        min(deceased_on)                                                   as deceased_on,
        count(*)                                                           as n_pims_records,
        string_agg(patient_source_key, ' | ' order by patient_source_key)  as pims_record_keys
    from records
    group by 1
),
app as (
    select p.pet_id, p.member_id, p.clinic_id, p.pet_name_raw, p.species, p.birth_date
    from {{ ref('stg_app__pets') }} p
)
select
    coalesce(f.golden_patient_id, md5('app:' || a.pet_id))                as golden_patient_id,
    a.pet_id                                                              as app_pet_id,
    a.member_id,
    coalesce(a.clinic_id, f.pims_clinic_id)                               as clinic_id,
    f.pims_clinic_id,
    coalesce(f.pims_pet_name, a.pet_name_raw)                             as pet_name,
    coalesce(f.species, a.species)                                        as species,
    f.breed,
    coalesce(f.pims_birth_date, a.birth_date)                             as birth_date,
    coalesce(f.is_deceased, false)                                        as is_deceased,
    f.deceased_on,
    a.pet_id is not null                                                  as is_plan_pet,
    case when a.pet_id is not null and f.golden_patient_id is null then 'not_found_in_pims'
         else f.match_rule end                                            as match_rule,
    f.match_confidence,
    coalesce(f.clinic_mismatch, false)                                    as clinic_mismatch,
    coalesce(f.n_pims_records, 0)                                         as n_pims_records,
    f.pims_record_keys
from from_pims f
full outer join app a on a.pet_id = f.app_pet_id
