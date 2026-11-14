-- Cross-reference: every PIMS patient record -> one golden patient id.
-- 1) records matched to an app pet share that pet's id
-- 2) a clinic that switched PIMS has the same animal in both systems: link the twins
-- 3) everything else stands on its own
with pims as (select * from {{ ref('int_pims_patients') }}),
matches as (select patient_source_key, pet_id, match_rule, match_confidence, clinic_mismatch from {{ ref('int_patient_matches') }}),
twin_candidates as (
    select o.patient_source_key as old_key, n.patient_source_key as new_key,
           row_number() over (partition by n.patient_source_key order by o.patient_source_key) as rn_new,
           row_number() over (partition by o.patient_source_key order by n.patient_source_key) as rn_old
    from pims o
    join pims n
      on o.clinic_id = n.clinic_id and o.practice_id <> n.practice_id and not o.is_current_feed and n.is_current_feed
     and o.species = n.species and o.pet_name_norm = n.pet_name_norm
     and (o.owner_email_norm = n.owner_email_norm or o.owner_phone_digits = n.owner_phone_digits
          or (o.owner_last_name_norm = n.owner_last_name_norm and o.owner_first_name_norm = n.owner_first_name_norm))
),
twins as (select old_key, new_key from twin_candidates where rn_new = 1 and rn_old = 1),
twin_pairs as (
    select old_key as k, new_key as twin_key, old_key as anchor_key from twins
    union all
    select new_key, old_key, old_key from twins
)
select
    p.patient_source_key,
    p.pims,
    p.practice_id,
    p.clinic_id,
    tp.twin_key                                                         as migration_twin_key,
    coalesce(m.pet_id, mt.pet_id)                                       as app_pet_id,
    coalesce(m.match_rule, mt.match_rule || '_via_migration_twin')      as match_rule,
    coalesce(m.match_confidence, mt.match_confidence)                   as match_confidence,
    coalesce(m.clinic_mismatch, mt.clinic_mismatch, false)              as clinic_mismatch,
    md5(case when coalesce(m.pet_id, mt.pet_id) is not null then 'app:' || coalesce(m.pet_id, mt.pet_id)
             else 'pims:' || coalesce(tp.anchor_key, p.patient_source_key) end) as golden_patient_id
from pims p
left join matches m on m.patient_source_key = p.patient_source_key
left join twin_pairs tp on tp.k = p.patient_source_key
left join matches mt on mt.patient_source_key = tp.twin_key
