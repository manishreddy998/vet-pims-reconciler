-- Entity resolution: which PIMS patient record is the same animal as each pet enrolled in the app?
-- Rules are explicit and ranked, so every match can be explained. Highest-confidence rule wins.
with app as (
    select
        p.pet_id, p.member_id, p.clinic_id, p.species, p.birth_date,
        -- people type the owner's surname into the pet name ("Bella Smith"): strip it
        trim(regexp_replace(p.pet_name_norm, ' ' || m.last_name_norm || '$', '')) as pet_name_core,
        m.email_norm, m.phone_digits, m.last_name_norm
    from {{ ref('stg_app__pets') }} p
    join {{ ref('stg_app__members') }} m using (member_id)
),
pims as (select * from {{ ref('int_pims_patients') }}),
candidates as (
    select
        a.pet_id, a.member_id, a.clinic_id as app_clinic_id, x.patient_source_key, x.pims, x.practice_id, x.clinic_id as pims_clinic_id,
        (a.email_norm is not null and a.email_norm = x.owner_email_norm)                  as email_match,
        (a.phone_digits is not null and a.phone_digits = x.owner_phone_digits)            as phone_match,
        (a.last_name_norm = x.owner_last_name_norm)                                       as owner_name_match,
        (a.pet_name_core = x.pet_name_norm
            or split_part(a.pet_name_core, ' ', 1) = split_part(x.pet_name_norm, ' ', 1)) as pet_name_match,
        {{ edit_distance('a.pet_name_core', 'x.pet_name_norm') }}                         as pet_name_distance,
        (a.birth_date is not null and x.birth_date is not null
            and abs(a.birth_date - x.birth_date) <= 45)                                   as dob_close,
        a.clinic_id = x.clinic_id                                                         as same_clinic
    from app a
    join pims x
      on a.species = x.species
     and (a.email_norm = x.owner_email_norm or a.phone_digits = x.owner_phone_digits or a.last_name_norm = x.owner_last_name_norm)
),
scored as (
    select *,
        case
            when same_clinic and email_match and pet_name_match                                 then 'email_and_pet_name'
            when same_clinic and phone_match and pet_name_match                                 then 'phone_and_pet_name'
            when same_clinic and (email_match or phone_match) and pet_name_distance <= 2        then 'contact_and_similar_pet_name'
            when same_clinic and owner_name_match and pet_name_match and dob_close              then 'owner_surname_pet_name_and_dob'
            when not same_clinic and (email_match or phone_match) and pet_name_match            then 'contact_and_pet_name_other_clinic'
        end as match_rule
    from candidates
),
ranked as (
    select *,
        case match_rule
            when 'email_and_pet_name' then 0.99
            when 'phone_and_pet_name' then 0.96
            when 'contact_and_similar_pet_name' then 0.90
            when 'owner_surname_pet_name_and_dob' then 0.85
            when 'contact_and_pet_name_other_clinic' then 0.75
        end as match_confidence
    from scored
    where match_rule is not null
),
best as (
    select *,
        row_number() over (partition by pet_id, practice_id order by match_confidence desc, patient_source_key) as rank_for_pet,
        row_number() over (partition by patient_source_key order by match_confidence desc, pet_id)            as rank_for_record
    from ranked
)
select pet_id, member_id, app_clinic_id, patient_source_key, pims, practice_id, pims_clinic_id,
       match_rule, match_confidence, not same_clinic as clinic_mismatch
from best
where rank_for_pet = 1 and rank_for_record = 1
