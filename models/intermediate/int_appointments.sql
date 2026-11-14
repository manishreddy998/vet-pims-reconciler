-- All appointments from all PIMS on one clock (UTC plus clinic-local), one status vocabulary,
-- and a decision on which system is the record of truth for that clinic on that date.
with unioned as (
    select 'cornerstone' as pims, a.appointment_source_key, a.patient_source_key, a.practice_id, a.pims_appointment_id,
           {{ local_to_utc('a.start_local', 'pr.clinic_timezone') }} as start_utc, a.start_local,
           a.appointment_type, a.duration_minutes, a.raw_status, a.source_updated_at_utc, a.n_versions, a.record_origin,
           pr.clinic_id, pr.active_from, pr.active_to
    from {{ ref('stg_cornerstone__appointments') }} a
    join {{ ref('int_practices') }} pr using (practice_id)
    union all
    select 'allydvm', a.appointment_source_key, a.patient_source_key, a.practice_id, a.pims_appointment_id,
           a.start_utc, {{ utc_to_local('a.start_utc', 'pr.clinic_timezone') }},
           a.appointment_type, a.duration_minutes, a.raw_status, a.source_updated_at_utc, a.n_versions, a.record_origin,
           pr.clinic_id, pr.active_from, pr.active_to
    from {{ ref('stg_allydvm__appointments') }} a
    join {{ ref('int_practices') }} pr using (practice_id)
),
mapped as (
    select u.*, s.canonical_status,
           cast(u.start_local as date) between u.active_from and coalesce(u.active_to, date '9999-12-31') as in_record_of_truth_window
    from unioned u
    left join {{ ref('appointment_status_map') }} s on s.pims = u.pims and s.raw_status = u.raw_status
)
select
    md5(m.appointment_source_key)                         as appointment_id,
    m.appointment_source_key, m.pims, m.practice_id, m.pims_appointment_id, m.clinic_id,
    x.golden_patient_id, m.patient_source_key,
    m.start_utc, m.start_local, cast(m.start_local as date) as local_date,
    m.appointment_type, m.duration_minutes, m.raw_status, m.canonical_status,
    case
        when m.canonical_status in ('scheduled', 'checked_in')
         and m.start_utc < ({{ dbt.current_timestamp() }} at time zone 'UTC') - interval '{{ var("stale_booking_hours") }} hours'
        then 'unresolved'
        else m.canonical_status
    end                                                   as resolved_status,
    m.record_origin, m.n_versions, m.source_updated_at_utc,
    m.in_record_of_truth_window                           as is_record_of_truth,
    case
        when m.in_record_of_truth_window then null
        when m.record_origin = 'imported' then 'superseded_imported_history'
        else 'orphaned_after_pims_migration'
    end                                                   as excluded_reason
from mapped m
left join {{ ref('int_patient_xref') }} x using (patient_source_key)
