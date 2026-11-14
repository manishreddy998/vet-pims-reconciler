-- Cornerstone re-exports every appointment on every extract. Keep the latest version, remember how many we saw.
with versions as (
    select
        *,
        cast(EXTRACTED_AT as timestamptz)                                                       as extracted_at_ts,
        row_number() over (partition by PRACTICE_ID, APPT_ID order by cast(EXTRACTED_AT as timestamptz) desc) as version_rank,
        count(*)     over (partition by PRACTICE_ID, APPT_ID)                                   as n_versions
    from {{ source('raw_cornerstone', 'appointments') }}
)
select
    'cs:' || PRACTICE_ID || ':' || APPT_ID        as appointment_source_key,
    'cs:' || PRACTICE_ID || ':' || PATIENT_ID     as patient_source_key,
    PRACTICE_ID                                   as practice_id,
    APPT_ID                                       as pims_appointment_id,
    {{ parse_us_timestamp('APPT_DATE', 'APPT_TIME') }} as start_local,  -- clinic wall-clock time, no zone
    lower(REASON)                                 as appointment_type,
    cast(DURATION_MIN as integer)                 as duration_minutes,
    STATUS                                        as raw_status,
    extracted_at_ts at time zone 'UTC'            as source_updated_at_utc,
    n_versions,
    'native'                                      as record_origin
from versions
where version_rank = 1
