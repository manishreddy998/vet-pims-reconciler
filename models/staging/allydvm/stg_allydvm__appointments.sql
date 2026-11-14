-- AllyDVM sends a new version of an appointment each time it changes. Latest updatedAt wins.
with versions as (
    select
        *,
        row_number() over (partition by practiceId, appointmentGuid order by cast(updatedAt as timestamptz) desc) as version_rank,
        count(*)     over (partition by practiceId, appointmentGuid)                                             as n_versions
    from {{ source('raw_allydvm', 'appointments') }}
)
select
    'ad:' || practiceId || ':' || appointmentGuid    as appointment_source_key,
    'ad:' || practiceId || ':' || patientGuid        as patient_source_key,
    practiceId                                       as practice_id,
    appointmentGuid                                  as pims_appointment_id,
    {{ iso_to_utc('startAt') }}                      as start_utc,  -- AllyDVM is UTC
    lower(type)                                      as appointment_type,
    cast(durationMinutes as integer)                 as duration_minutes,
    status                                           as raw_status,
    {{ iso_to_utc('updatedAt') }}                    as source_updated_at_utc,
    n_versions,
    case when source like 'import:%' then 'imported' else 'native' end as record_origin
from versions
where version_rank = 1
